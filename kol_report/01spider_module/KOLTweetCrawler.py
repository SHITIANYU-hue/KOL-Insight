#!/usr/bin/env python3
# KOLTweetCrawler.py - 专门用于抓取指定KOL的推文
# 基于原1.py修改，简化为只抓取指定KOL的推文

import aiohttp
import asyncio
import time
import json
import logging
import sqlite3
import os
import argparse
import traceback
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional, Set

class KOLTweetCrawler:
    def __init__(self, api_key: str, db_dir: str):
        self.api_key = api_key
        self.base_url = "https://api.tweetscout.io/v2"
        self.db_dir = db_dir
        # tweets.db的路径
        self.tweets_db_path = os.path.join(self.db_dir, "tweets.db")
        # followingA.db的路径
        self.following_db_path = os.path.join(self.db_dir, "followingA.db")
        self.headers = {
            "ApiKey": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self._setup_logging()
        # 初始化数据库
        self.conn = None
        self.cursor = None
        self._init_database()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s'
        )
        self.logger = logging.getLogger("KOLTweetCrawler")

    def _init_database(self):
        """初始化用于存储推文和评论的数据库 (tweets.db)"""
        try:
            # 确保目录存在
            os.makedirs(self.db_dir, exist_ok=True)
            
            # 删除旧数据库（如果存在）
            if os.path.exists(self.tweets_db_path):
                backup_path = f"{self.tweets_db_path}.{int(time.time())}.bak"
                os.rename(self.tweets_db_path, backup_path)
                self.logger.info(f"已备份现有数据库到 {backup_path}")
            
            # 连接tweets.db
            self.conn = sqlite3.connect(self.tweets_db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES, timeout=10)
            self.cursor = self.conn.cursor()
            self.conn.execute("PRAGMA journal_mode=WAL;")  # 提高并发性
            self.conn.execute("PRAGMA busy_timeout = 5000;") # 锁定时等待5秒

            # 创建tweets表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS tweets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE NOT NULL,
                    conversation_id TEXT,
                    author_id TEXT NOT NULL,
                    author_name TEXT,
                    full_text TEXT,
                    created_at TIMESTAMP,
                    likes_count INTEGER DEFAULT 0,
                    retweets_count INTEGER DEFAULT 0,
                    replies_count INTEGER DEFAULT 0,
                    views_count INTEGER DEFAULT 0,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    bookmark_count INTEGER DEFAULT 0,
                    in_reply_to_status_id_str TEXT,
                    is_quote_status INTEGER DEFAULT 0,
                    quote_count INTEGER DEFAULT 0,
                    entities TEXT,
                    quoted_status TEXT,
                    retweeted_status TEXT,
                    user TEXT
                )
            ''')

            # 创建comments表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT NOT NULL,
                    comment_id TEXT UNIQUE NOT NULL,
                    author_id TEXT,
                    comment_text TEXT,
                    created_at TIMESTAMP,
                    likes_count INTEGER DEFAULT 0,
                    FOREIGN KEY (tweet_id) REFERENCES tweets(tweet_id) ON DELETE CASCADE
                )
            ''')
            # 创建tweets表索引
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_author_id ON tweets(author_id)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_created_at ON tweets(created_at)')
            # 创建comments表索引
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_comment_tweet_id ON comments(tweet_id)')

            self.conn.commit()
            self.logger.info(f"推文数据库 {self.tweets_db_path} 初始化成功")

        except sqlite3.Error as e:
            self.logger.error(f"初始化推文数据库 {self.tweets_db_path} 失败: {e}")
            if self.conn:
                self.conn.close()
            self.conn = None
            self.cursor = None
        except Exception as e:
            self.logger.error(f"初始化推文数据库时发生意外错误: {e}")
            if self.conn:
                self.conn.close()
            self.conn = None
            self.cursor = None

    def load_kol_authors(self) -> List[Dict]:
        """从followingA.db加载KOL作者信息"""
        authors = []
        conn_following = None
        try:
            # 检查文件是否存在
            if not os.path.exists(self.following_db_path):
                self.logger.error(f"源数据库文件未找到: {self.following_db_path}. 无法加载KOL作者。")
                return []

            # 连接followingA.db
            conn_following = sqlite3.connect(self.following_db_path, timeout=10)
            conn_following.execute("PRAGMA query_only = ON;") # 只读访问
            cursor = conn_following.cursor()

            # 检查users表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone() is None:
                self.logger.error(f"数据库中未找到'users'表: {self.following_db_path}. 无法加载KOL作者。")
                return []

            # 获取所有KOL作者
            cursor.execute("SELECT username, user_id FROM users WHERE user_id IS NOT NULL AND user_id != ''")
            rows = cursor.fetchall()
            
            # 过滤可能的重复项
            seen_ids = set()
            for row in rows:
                user_id = row[1]
                if user_id not in seen_ids:
                    authors.append({"username": row[0], "author_id": user_id})
                    seen_ids.add(user_id)

            if authors:
                sample_authors = [a.get('username', 'N/A') for a in authors[:5]]
                self.logger.info(f"从数据库 {self.following_db_path} 加载了 {len(authors)} 个KOL作者。示例: {sample_authors}...")
            else:
                self.logger.warning(f"在数据库中未找到有效的KOL作者: {self.following_db_path}")
            return authors

        except sqlite3.Error as e:
            self.logger.error(f"从 {self.following_db_path} 加载作者时数据库错误: {e}")
            return []
        except Exception as e:
            self.logger.error(f"从 {self.following_db_path} 加载作者时意外错误: {e}")
            return []
        finally:
            # 确保关闭followingA.db连接
            if conn_following:
                conn_following.close()

    async def get_tweet_comments(self, tweet_id: str, conversation_id: str, session: aiohttp.ClientSession) -> List[Dict]:
        """获取推文的评论"""
        all_comments = []
        if not conversation_id:
            self.logger.warning(f"无法为推文 {tweet_id} 提供conversation_id，无法获取评论。")
            return all_comments

        try:
            url = f"{self.base_url}/search-tweets"
            query = f"conversation_id:{conversation_id}"
            next_cursor = ""
            max_comment_pages = 5 # 限制页数以防止对热门推文过度调用

            for page in range(max_comment_pages):
                data = {
                    "query": query,
                    "next_cursor": next_cursor
                }
                try:
                    # 使用提供的会话
                    async with session.post(url, headers=self.headers, json=data, timeout=60) as response:
                        if response.status == 200:
                            response_text = await response.text()
                            if not response_text.strip():
                                self.logger.warning(f"API返回空响应，查询: {query}, 页: {page+1}")
                                break
                            try:
                                response_data = json.loads(response_text)
                            except json.JSONDecodeError:
                                self.logger.error(f"API返回无效JSON，查询: {query}. 页: {page+1}. 响应: {response_text[:200]}...")
                                break

                            comments = response_data.get("tweets", [])
                            if not comments:
                                self.logger.debug(f"对话 {conversation_id} 未找到更多评论, 页: {page+1}")
                                break

                            # 过滤原始推文并确保它是对话的一部分
                            filtered_comments = [
                                c for c in comments
                                if c.get("id_str") != tweet_id and c.get("conversation_id_str") == conversation_id
                            ]
                            all_comments.extend(filtered_comments)
                            self.logger.debug(f"为推文 {tweet_id} 获取到 {len(filtered_comments)} 条新评论，页 {page+1} (现在总计: {len(all_comments)})")

                            next_cursor = response_data.get("next_cursor")
                            if not next_cursor:
                                self.logger.debug(f"对话 {conversation_id} 没有下一页游标。结束评论获取。")
                                break
                            await asyncio.sleep(2) # 页面之间的速率限制

                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 60))
                            self.logger.warning(f"速率限制 (429) 获取评论页 {page+1}，推文 {tweet_id}。等待 {retry_after} 秒...")
                            await asyncio.sleep(retry_after)
                            continue # 重试同一页

                        else:
                            error_text = await response.text()
                            self.logger.error(f"获取评论页 {page+1}，推文 {tweet_id} 时API错误: 状态 {response.status}, {error_text[:200]}...")
                            break # 发生错误时停止获取此推文的评论

                except asyncio.TimeoutError:
                    self.logger.error(f"获取评论页 {page+1}，推文 {tweet_id} 超时。")
                    break # 超时时停止获取此推文的评论
                except aiohttp.ClientError as client_err:
                    self.logger.error(f"获取评论页 {page+1}，推文 {tweet_id} 网络错误: {client_err}")
                    break # 网络错误时停止获取此推文的评论

                # 处理最大页数
                if page == max_comment_pages - 1 and next_cursor:
                    self.logger.warning(f"达到最大评论页限制 ({max_comment_pages})，推文 {tweet_id}。")

            self.logger.debug(f"完成获取推文 {tweet_id} 的评论。总共找到: {len(all_comments)}")
            return all_comments

        except Exception as e:
            self.logger.error(f"搜索推文 {tweet_id} 的评论时意外错误: {e}")
            self.logger.error(traceback.format_exc())
            return [] # 出现意外错误时返回空列表

    def save_comment(self, tweet_id: str, comment_data: Dict):
        """将评论保存到tweets.db"""
        if not self.conn or not self.cursor:
            self.logger.error("数据库连接不可用，无法保存评论。")
            return
        try:
            created_at_dt = None
            created_at_str = comment_data.get('created_at')
            if created_at_str:
                try:
                    # 确保一致的UTC时区
                    created_at_dt = parsedate_to_datetime(created_at_str)
                    # 如果时区存在但不需要，则使时间为naive
                    if created_at_dt.tzinfo:
                        created_at_dt = created_at_dt.replace(tzinfo=None)
                except Exception:
                    self.logger.warning(f"无法解析评论日期: {created_at_str}")

            self.cursor.execute('''
                INSERT OR IGNORE INTO comments
                (tweet_id, comment_id, author_id, comment_text, created_at, likes_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                tweet_id,
                comment_data.get('id_str'),
                comment_data.get('user', {}).get('id_str'),
                comment_data.get('full_text', ''),
                created_at_dt, # 存储datetime对象
                comment_data.get('favorite_count', 0)
            ))
            # 在process_author或run循环中处理提交以提高效率
        except sqlite3.Error as e:
            self.logger.error(f"保存推文 {tweet_id} 的评论时数据库错误: {e}")
        except Exception as e:
            self.logger.error(f"保存评论时意外错误: {e}")

    async def get_user_tweets(self, author_id: str, max_tweets: int, session: aiohttp.ClientSession) -> List[Dict]:
        """获取用户的推文"""
        all_tweets = []
        if not author_id:
            self.logger.warning("未提供author_id，无法获取推文。")
            return all_tweets
        try:
            url = f"{self.base_url}/user-tweets"
            cursor = ""
            pages_fetched = 0
            max_pages = (max_tweets // 20) + 2 # 估计需要的页数

            while len(all_tweets) < max_tweets and pages_fetched < max_pages:
                pages_fetched += 1
                data = {
                    "user_id": author_id,
                    "cursor": cursor
                }
                try:
                    # 使用提供的会话
                    async with session.post(url, headers=self.headers, json=data, timeout=60) as response:
                        if response.status == 200:
                            try:
                                response_data = await response.json()
                            except json.JSONDecodeError:
                                response_text = await response.text()
                                self.logger.error(f"获取用户 {author_id} 的推文时API返回无效JSON, 页 {pages_fetched}. 响应: {response_text[:200]}...")
                                break

                            tweets = response_data.get('tweets', [])
                            if not tweets:
                                self.logger.debug(f"用户 {author_id} 没有更多推文, 页 {pages_fetched}")
                                break

                            all_tweets.extend(tweets)
                            self.logger.debug(f"为用户 {author_id} 获取到 {len(tweets)} 条推文，页 {pages_fetched} (现在总计: {len(all_tweets)}/{max_tweets})")

                            if len(all_tweets) >= max_tweets:
                                all_tweets = all_tweets[:max_tweets]
                                self.logger.info(f"达到max_tweets ({max_tweets})，用户 {author_id}。")
                                break

                            cursor = response_data.get('next_cursor')
                            if not cursor:
                                self.logger.debug(f"用户 {author_id} 没有提供下一页游标。结束推文获取。")
                                break
                            await asyncio.sleep(2) # 页面之间的速率限制

                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 60))
                            self.logger.warning(f"速率限制 (429) 获取推文页 {pages_fetched}，用户 {author_id}。等待 {retry_after} 秒...")
                            await asyncio.sleep(retry_after)
                            pages_fetched -= 1 # 重试同一页时减少页数
                            continue # 重试同一页

                        elif response.status == 404:
                            self.logger.warning(f"API未找到用户 {author_id} (404)。")
                            break
                        else:
                            error_text = await response.text()
                            self.logger.error(f"获取推文页 {pages_fetched}，用户 {author_id} 时API错误: 状态 {response.status}, {error_text[:200]}...")
                            break # 发生错误时停止获取此用户的推文

                except asyncio.TimeoutError:
                    self.logger.error(f"获取推文页 {pages_fetched}，用户 {author_id} 超时。")
                    break # 超时时停止获取此用户的推文
                except aiohttp.ClientError as client_err:
                    self.logger.error(f"获取推文页 {pages_fetched}，用户 {author_id} 网络错误: {client_err}")
                    break # 网络错误时停止获取此用户的推文

            self.logger.info(f"总共为用户ID {author_id} 获取到 {len(all_tweets)} 条推文")
            return all_tweets

        except Exception as e:
            self.logger.error(f"获取用户ID {author_id} 的推文时意外错误: {e}")
            self.logger.error(traceback.format_exc())
            return []

    def save_tweet(self, author: Dict, tweet_data: Dict):
        """将推文保存到tweets.db"""
        if not self.conn or not self.cursor:
            self.logger.error("数据库连接不可用，无法保存推文。")
            return
        try:
            created_at_dt = None
            created_at_str = tweet_data.get('created_at')
            if created_at_str:
                try:
                    created_at_dt = parsedate_to_datetime(created_at_str)
                    if created_at_dt.tzinfo:
                        created_at_dt = created_at_dt.replace(tzinfo=None)
                except Exception:
                    self.logger.warning(f"无法解析推文日期: {created_at_str}")
            # 将复杂对象序列化为JSON字符串（2.0版本修改）
            entities_json = None
            if tweet_data.get('entities'):
                try:
                    entities_json = json.dumps(tweet_data['entities'], ensure_ascii=False)
                except Exception as e:
                    self.logger.warning(f"序列化entities失败: {e}")

            quoted_status_json = None
            if tweet_data.get('quoted_status'):
                try:
                    quoted_status_json = json.dumps(tweet_data['quoted_status'], ensure_ascii=False)
                except Exception as e:
                    self.logger.warning(f"序列化quoted_status失败: {e}")

            retweeted_status_json = None
            if tweet_data.get('retweeted_status'):
                try:
                    retweeted_status_json = json.dumps(tweet_data['retweeted_status'], ensure_ascii=False)
                except Exception as e:
                    self.logger.warning(f"序列化retweeted_status失败: {e}")

            user_json = None
            if tweet_data.get('user'):
                try:
                    user_json = json.dumps(tweet_data['user'], ensure_ascii=False)
                except Exception as e:
                    self.logger.warning(f"序列化user失败: {e}")
            # test_api = None
            # try:
            #     test_api = json.dumps(tweet_data, ensure_ascii=False)
            # except Exception as e:
            #     self.logger.warning(f"序列化tweet_data失败: {e}")
            self.cursor.execute('''
                INSERT OR REPLACE INTO tweets
                (tweet_id, conversation_id, author_id, author_name, full_text, created_at,
                 likes_count, retweets_count, replies_count, views_count, collected_at,
                 bookmark_count, in_reply_to_status_id_str, is_quote_status, quote_count,
                 entities, quoted_status, retweeted_status, user)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tweet_data.get('id_str'),
                tweet_data.get('conversation_id_str'),
                author['author_id'],
                author['username'],
                tweet_data.get('full_text', ''),
                created_at_dt, # 存储datetime对象
                tweet_data.get('favorite_count', 0),
                tweet_data.get('retweet_count', 0),
                tweet_data.get('reply_count', 0),
                tweet_data.get('view_count', 0),
                # 新增字段
                tweet_data.get('bookmark_count', 0),
                tweet_data.get('in_reply_to_status_id_str'),
                1 if tweet_data.get('is_quote_status', False) else 0,
                tweet_data.get('quote_count', 0),
                entities_json,
                quoted_status_json,
                retweeted_status_json,
                user_json
            ))
            # 提交在process_author或run循环中处理
        except sqlite3.Error as e:
            self.logger.error(f"保存作者 {author['username']} 的推文 {tweet_data.get('id_str')} 时数据库错误: {e}")
        except Exception as e:
            self.logger.error(f"保存推文时意外错误: {e}")

    async def process_author(self, author: Dict, max_tweets: int, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession, skip_comments: bool = False):
        """处理单个作者的推文和评论"""
        author_id = author.get('author_id')
        author_name = author.get('username', 'N/A')
        if not author_id:
            self.logger.warning(f"由于缺少author_id，跳过作者: {author}")
            return
        async with semaphore:
            self.logger.info(f"开始处理作者的推文: {author_name} ({author_id})")
            processed_tweets = 0
            processed_comments = 0
            try:
                # 获取作者的推文
                tweets = await self.get_user_tweets(author_id, max_tweets, session)
                self.logger.info(f"处理为作者 {author_name} 找到的 {len(tweets)} 条推文")

                for tweet in tweets:
                    # 保存推文
                    self.save_tweet(author, tweet)
                    processed_tweets += 1

                    # 判断是否要跳过评论
                    if skip_comments:
                        self.logger.debug(f"跳过获取作者{author_name}的推文")
                        continue
                    # 获取conversation_id和tweet_id以获取评论
                    conversation_id = tweet.get("conversation_id_str")
                    tweet_id = tweet.get("id_str")

                    if conversation_id and tweet_id and tweet.get('reply_count', 0) > 0: # 只在reply_count > 0时获取评论
                        # 获取并保存评论
                        comments = await self.get_tweet_comments(tweet_id, conversation_id, session)
                        if comments:
                            self.logger.debug(f"保存推文 {tweet_id} 的 {len(comments)} 条评论，作者 {author_name}")
                            for comment in comments:
                                self.save_comment(tweet_id, comment)
                                processed_comments += 1
                        else:
                            self.logger.debug(f"未找到或未获取推文 {tweet_id} 的评论，作者 {author_name}")
                    else:
                        self.logger.debug(f"跳过获取推文 {tweet_id} 的评论 (缺少conversation_id/tweet_id或无回复)。")

                    # 处理同一作者的推文之间的可选短暂休眠
                    await asyncio.sleep(0.2) # 较短的休眠

                # 处理完所有推文和评论后为此作者提交事务
                if self.conn:
                    self.conn.commit()

            except Exception as e:
                self.logger.error(f"处理作者 {author_name} ({author_id}) 时出错: {e}")
                self.logger.error(traceback.format_exc())
                # 错误发生时回滚此作者的潜在部分更改
                if self.conn:
                    self.conn.rollback()
            finally:
                self.logger.info(f"完成作者 {author_name} ({author_id}) 的推文处理。保存了 {processed_tweets} 条推文, {processed_comments} 条评论。")
    
    async def run(self, max_tweets: int, max_concurrent_tasks: int = 5, skip_comments: bool = False):
        """运行推文收集爬虫"""
        if not self.conn:
            self.logger.error("推文数据库连接不可用。中止推文收集。")
            return
        run_start_time = time.time()
        self.logger.info(f"--- 开始推文收集 (每个KOL最多 {max_tweets} 条推文, 并发数: {max_concurrent_tasks}) ---")
        try:
            authors = self.load_kol_authors()
            if not authors:
                self.logger.warning("未加载KOL作者，跳过推文收集。")
                return

            semaphore = asyncio.Semaphore(max_concurrent_tasks)
            self.logger.info(f"处理 {len(authors)} 个KOL作者...")

            # 创建单个aiohttp会话供所有任务重用
            async with aiohttp.ClientSession() as session:
                tasks = []
                for author in authors:
                    # 为每个作者安排处理任务
                    task = asyncio.create_task(self.process_author(author, max_tweets, semaphore, session, skip_comments))
                    tasks.append(task)

                # 等待所有任务完成
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    # 记录任务中发生的任何异常
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            self.logger.error(f"作者 {authors[i].get('username', 'N/A')} 的任务出错: {result}")
                    self.logger.info("所有作者推文处理任务已完成(或失败)。")
                else:
                    self.logger.info("未安排作者任务。")

        except Exception as e:
            self.logger.error(f"主推文爬虫运行期间发生错误: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            # 确保关闭主连接(到tweets.db)
            if hasattr(self, 'conn') and self.conn:
                try:
                    self.conn.close()
                    self.logger.info(f"推文数据库 {self.tweets_db_path} 连接已关闭。")
                except Exception as close_err:
                    self.logger.error(f"关闭推文数据库连接时错误: {close_err}")
            run_end_time = time.time()
            self.logger.info(f"--- 推文收集完成 (持续时间: {run_end_time - run_start_time:.2f} 秒) ---")

def main():
    parser = argparse.ArgumentParser(description="KOLTweetCrawler - 专门用于抓取指定KOL的推文")
    parser.add_argument("--max_tweets", type=int, default=100, help="每个KOL的最大推文数")
    parser.add_argument("--db_dir", type=str, required=True, help="包含followingA.db的目录以及用于创建tweets.db的目录")
    parser.add_argument("--api_key", type=str, default="tweetscout api", help="TweetScout API密钥")
    parser.add_argument("--max_concurrent_tasks", type=int, default=5, help="并发作者任务数")
    parser.add_argument("--skip_comments", action="store_true", help="跳过抓取推文评论")
    args = parser.parse_args()

    print(f"使用db_dir运行KOLTweetCrawler: {args.db_dir}")
    # 从环境变量安全加载API密钥
    api_key = os.getenv("TWEETSCOUT_API_KEY", args.api_key)
    if api_key == "tweetscout api": 
        print("警告: 使用默认API密钥运行。")

    crawler = KOLTweetCrawler(
        api_key=api_key,
        db_dir=args.db_dir
    )
    asyncio.run(crawler.run(args.max_tweets, max_concurrent_tasks=args.max_concurrent_tasks, skip_comments=args.skip_comments))

if __name__ == "__main__":
    main()