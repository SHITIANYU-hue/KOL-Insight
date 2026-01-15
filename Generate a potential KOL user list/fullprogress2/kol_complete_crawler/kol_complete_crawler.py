"""
KOL 完整爬虫程序
================

功能：
- 从指定的 KOL_yes.db 文件中读取所有用户信息
- 爬取每个用户的推文数据
- 爬取推文的评论数据（可选）
- 将数据保存到同目录下的 KOL_tweets.db 文件中

使用方法：
1. 基本使用（爬取全部数据）：
   python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --max_tweets 0 --max_comments_per_tweet 0

2. 限制数量爬取：
   python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --max_tweets 100 --max_comments_per_tweet 50

3. 只爬取推文，不爬取评论：
   python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --no_comments

4. 查看统计信息：
   python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --stats_only

5. 自定义并发设置：
   python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --max_tweet_tasks 20 --max_comment_tasks 5

参数说明：
- --kol_db_path: 必需，KOL_yes.db 文件的完整路径
- --max_tweets: 每用户最大推文数，0表示全部
- --max_comments_per_tweet: 每推文最大评论数，0表示全部
- --no_comments: 不收集评论
- --max_tweet_tasks: 推文爬取的并发任务数，默认20
- --max_comment_tasks: 评论爬取的并发任务数，默认5
- --api_key: TweetScout API 密钥
"""

import aiohttp
import asyncio
import time
import json
import logging
import sqlite3
import os
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional, Callable, Any
import argparse
import traceback
from functools import wraps

class RateLimiter:
    """API请求限速器，控制请求速率避免触发429错误"""
    def __init__(self, requests_per_second: float = 2.0):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0
        self.lock = asyncio.Lock()
        
    async def acquire(self):
        """获取请求许可，必要时等待以满足速率限制"""
        async with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            
            # 如果距离上次请求时间不足最小间隔，则等待
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                await asyncio.sleep(wait_time)
                
            self.last_request_time = time.time()

def retry_on_error(max_retries: int = 3, backoff_factor: float = 1.0):
    """重试装饰器，用于处理API请求错误"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(self, *args, **kwargs)
                except asyncio.TimeoutError as e:
                    retries += 1
                    if retries == max_retries:
                        self.logger.error(f"最终超时错误: {str(e)}")
                        raise
                    wait_time = backoff_factor * (2 ** (retries - 1))
                    self.logger.warning(f"超时错误，第{retries}次重试，等待{wait_time}秒...")
                    await asyncio.sleep(wait_time)
                except aiohttp.ClientError as e:
                    retries += 1
                    if retries == max_retries:
                        self.logger.error(f"最终网络错误: {str(e)}")
                        raise
                    wait_time = backoff_factor * (2 ** (retries - 1))
                    self.logger.warning(f"网络错误，第{retries}次重试，等待{wait_time}秒...")
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    self.logger.error(f"未预期的错误: {str(e)}")
                    raise
        return wrapper
    return decorator

class KOLCompleteCrawler:
    def __init__(self, api_key: str, kol_db_path: str):
        self.api_key = api_key
        self.base_url = "https://api.tweetscout.io/v2"
        
        # 数据库路径设置
        self.kol_yes_db_path = kol_db_path
        # 获取数据库文件所在的目录
        self.db_dir = os.path.dirname(kol_db_path)
        # 如果db_dir为空（即只提供了文件名），将其设置为当前目录
        if not self.db_dir:
            self.db_dir = "."
        # 在同一目录下创建输出数据库
        self.kol_tweets_db_path = os.path.join(self.db_dir, "KOL_tweets.db")
        
        self.headers = {
            "ApiKey": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "KOLCompleteCrawler/1.0"  # 添加User-Agent
        }
        
        # 性能优化：增加批量提交大小
        self.batch_size = 50  # 每50条记录提交一次
        self.tweet_batch_counter = 0
        self.comment_batch_counter = 0
        
        # 添加请求限速器
        self.tweet_rate_limiter = RateLimiter(requests_per_second=5.0)  # 每秒最多5个推文请求
        self.comment_rate_limiter = RateLimiter(requests_per_second=5.0)  # 每秒最多5个评论请求
        
        self._setup_logging()
        self.kol_yes_conn = None
        self.kol_tweets_conn = None
        self.kol_tweets_cursor = None
        
        # 初始化数据库连接
        self._init_databases()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s'
        )
        self.logger = logging.getLogger("KOLCompleteCrawler")

    def _init_databases(self):
        """初始化数据库连接和创建必要的表"""
        try:
            # 检查源数据库文件是否存在
            if not os.path.exists(self.kol_yes_db_path):
                self.logger.error(f"源数据库文件不存在: {self.kol_yes_db_path}")
                return
                
            # 确保输出目录存在
            os.makedirs(self.db_dir, exist_ok=True)
            
            # 连接 KOL_yes.db (只读)
            self.kol_yes_conn = sqlite3.connect(
                self.kol_yes_db_path, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES, 
                timeout=10
            )
            self.kol_yes_conn.execute("PRAGMA query_only = ON;")  # 只读模式
            self.logger.info(f"成功连接到源数据库: {self.kol_yes_db_path}")
            
            # 连接/创建 KOL_tweets.db (用于存储爬取的推文和评论)
            self.kol_tweets_conn = sqlite3.connect(
                self.kol_tweets_db_path, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES, 
                timeout=10
            )
            self.kol_tweets_cursor = self.kol_tweets_conn.cursor()
            
            # 性能优化：改进SQLite设置
            self.kol_tweets_conn.execute("PRAGMA journal_mode=WAL;")  # 提高并发性
            self.kol_tweets_conn.execute("PRAGMA synchronous=NORMAL;")  # 减少同步IO，提高写入速度
            self.kol_tweets_conn.execute("PRAGMA cache_size=10000;")  # 增加缓存大小
            self.kol_tweets_conn.execute("PRAGMA busy_timeout = 5000;")  # 锁定时等待5秒
            
            # 创建推文表
            self.kol_tweets_cursor.execute('''
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
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建评论表
            self.kol_tweets_cursor.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT NOT NULL,
                    comment_id TEXT UNIQUE NOT NULL,
                    author_id TEXT,
                    author_name TEXT,
                    comment_text TEXT,
                    created_at TIMESTAMP,
                    likes_count INTEGER DEFAULT 0,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tweet_id) REFERENCES tweets(tweet_id) ON DELETE CASCADE
                )
            ''')
            
            # 创建用户处理记录表
            self.kol_tweets_cursor.execute('''
                CREATE TABLE IF NOT EXISTS processing_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    username TEXT,
                    tweets_collected INTEGER DEFAULT 0,
                    comments_collected INTEGER DEFAULT 0,
                    last_processed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            
            # 创建索引
            self.kol_tweets_cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_author_id ON tweets(author_id)')
            self.kol_tweets_cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_created_at ON tweets(created_at)')
            self.kol_tweets_cursor.execute('CREATE INDEX IF NOT EXISTS idx_comment_tweet_id ON comments(tweet_id)')
            self.kol_tweets_cursor.execute('CREATE INDEX IF NOT EXISTS idx_comment_author_id ON comments(author_id)')
            
            self.kol_tweets_conn.commit()
            self.logger.info(f"KOL推文数据库 {self.kol_tweets_db_path} 初始化完成")
            
        except sqlite3.Error as e:
            self.logger.error(f"数据库初始化失败: {e}")
            self._close_connections()
        except Exception as e:
            self.logger.error(f"初始化过程中发生未预期错误: {e}")
            self._close_connections()

    def _close_connections(self):
        """关闭所有数据库连接"""
        try:
            if self.kol_yes_conn:
                self.kol_yes_conn.close()
                self.kol_yes_conn = None
            if self.kol_tweets_conn:
                self.kol_tweets_conn.close()
                self.kol_tweets_conn = None
                self.kol_tweets_cursor = None
            self.logger.info("所有数据库连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭数据库连接时发生错误: {e}")

    def load_kol_users(self) -> List[Dict]:
        """从 KOL_yes.db 加载所有用户信息"""
        users = []
        try:
            if not self.kol_yes_conn:
                self.logger.error("KOL_yes.db 连接不可用")
                return []

            cursor = self.kol_yes_conn.cursor()
            
            # 检查 users 表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone() is None:
                self.logger.error("KOL_yes.db 中没有 users 表")
                return []
            
            # 首先查看表结构
            cursor.execute("PRAGMA table_info(users)")
            columns_info = cursor.fetchall()
            available_columns = [col[1] for col in columns_info]
            self.logger.info(f"users 表的可用列: {available_columns}")
            
            # 根据实际列名构建查询
            # 从截图看，应该有这些列：username, screen_name, description, followers_count, friends_count
            query_columns = []
            select_fields = []
            
            # 检查是否有 user_id 或类似的主键列
            if 'user_id' in available_columns:
                query_columns.append('user_id')
                select_fields.append('user_id')
            elif 'id' in available_columns:
                query_columns.append('id')
                select_fields.append('id')
            elif 'rowid' in available_columns:
                query_columns.append('rowid')
                select_fields.append('rowid')
            else:
                # 如果没有明确的ID列，使用username作为唯一标识
                query_columns.append('username')
                select_fields.append('username')
                
            # 添加其他必要的列
            essential_columns = ['username', 'screen_name', 'description', 'followers_count', 'friends_count']
            for col in essential_columns:
                if col in available_columns and col not in query_columns:
                    query_columns.append(col)
                    select_fields.append(col)
            
            # 构建查询语句
            query = f"SELECT {', '.join(query_columns)} FROM users"
            
            # 添加排序条件
            if 'followers_count' in available_columns:
                query += " ORDER BY followers_count DESC"
                
            self.logger.info(f"执行查询: {query}")
            cursor.execute(query)
            rows = cursor.fetchall()
            
            for row in rows:
                user_data = {}
                for i, field in enumerate(select_fields):
                    user_data[field] = row[i]
                
                # 确保有必要的字段
                if 'user_id' not in user_data:
                    # 如果没有user_id，尝试使用其他字段作为ID
                    if 'id' in user_data:
                        user_data['user_id'] = str(user_data['id'])
                    elif 'rowid' in user_data:
                        user_data['user_id'] = str(user_data['rowid'])
                    else:
                        # 最后使用username作为ID（这不是最佳做法，但可以工作）
                        user_data['user_id'] = user_data.get('username', '')
                
                # 确保有username
                if 'username' not in user_data:
                    user_data['username'] = user_data.get('screen_name', 'unknown')
                
                # 设置默认值
                user_data.setdefault('screen_name', user_data.get('username', ''))
                user_data.setdefault('description', '')
                user_data.setdefault('followers_count', 0)
                user_data.setdefault('friends_count', 0)
                
                users.append(user_data)
                
            self.logger.info(f"从 KOL_yes.db 中加载了 {len(users)} 个用户")
            if users:
                sample_users = [f"{u.get('username', 'N/A')}({u.get('followers_count', 0)})" for u in users[:5]]
                self.logger.info(f"示例用户: {sample_users}")
                
            return users
            
        except sqlite3.Error as e:
            self.logger.error(f"加载用户信息时发生数据库错误: {e}")
            return []
        except Exception as e:
            self.logger.error(f"加载用户信息时发生未预期错误: {e}")
            return []

    @retry_on_error(max_retries=3, backoff_factor=1.0)
    async def get_user_tweets(self, user_id: str, max_tweets: int, session: aiohttp.ClientSession) -> List[Dict]:
        """获取用户推文"""
        all_tweets = []
        if not user_id:
            self.logger.warning("未提供 user_id，无法获取推文")
            return all_tweets
            
        try:
            url = f"{self.base_url}/user-tweets"
            cursor = ""
            pages_fetched = 0
            max_pages = (max_tweets // 50) + 2 if max_tweets > 0 else 20  # 如果是爬取全部，限制最大页数
            
            while (max_tweets == 0 or len(all_tweets) < max_tweets) and pages_fetched < max_pages:
                pages_fetched += 1
                data = {
                    "user_id": user_id,
                    "cursor": cursor
                }
                
                try:
                    # 使用推文限速器控制请求速率
                    await self.tweet_rate_limiter.acquire()
                    
                    async with session.post(url, headers=self.headers, json=data, timeout=120) as response:
                        if response.status == 200:
                            try:
                                response_data = await response.json()
                            except json.JSONDecodeError:
                                response_text = await response.text()
                                self.logger.error(f"API 返回无效 JSON，用户 {user_id}，页 {pages_fetched}. 响应: {response_text[:200]}...")
                                break

                            tweets = response_data.get('tweets', [])
                            if not tweets:
                                self.logger.debug(f"用户 {user_id} 第 {pages_fetched} 页没有更多推文")
                                break

                            all_tweets.extend(tweets)
                            self.logger.debug(f"用户 {user_id} 第 {pages_fetched} 页获取 {len(tweets)} 条推文 (总计: {len(all_tweets)})")

                            if max_tweets > 0 and len(all_tweets) >= max_tweets:
                                all_tweets = all_tweets[:max_tweets]
                                self.logger.info(f"用户 {user_id} 达到最大推文数 ({max_tweets})")
                                break

                            cursor = response_data.get('next_cursor')
                            if not cursor:
                                self.logger.debug(f"用户 {user_id} 没有下一页，结束推文获取")
                                break
                                
                            await asyncio.sleep(0.5)  # 页面间限速

                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 60))
                            self.logger.warning(f"获取用户 {user_id} 推文第 {pages_fetched} 页时被限速 (429)。等待 {retry_after} 秒...")
                            # 轻微调整请求速率
                            self.tweet_rate_limiter.requests_per_second *= 0.9  # 降低10%的请求速率
                            self.tweet_rate_limiter.min_interval = 1.0 / self.tweet_rate_limiter.requests_per_second
                            self.logger.info(f"轻微调整推文请求速率为每秒 {self.tweet_rate_limiter.requests_per_second:.2f} 请求")
                            await asyncio.sleep(retry_after)
                            pages_fetched -= 1  # 重试同一页
                            continue

                        elif response.status == 404:
                            self.logger.warning(f"用户 {user_id} 未找到 (404)")
                            break
                            
                        else:
                            error_text = await response.text()
                            self.logger.error(f"获取用户 {user_id} 推文第 {pages_fetched} 页时 API 错误: 状态 {response.status}, {error_text[:200]}...")
                            
                            # 对500错误进行重试处理
                            if response.status == 500:
                                retry_wait = 5  # 等待5秒后重试
                                self.logger.warning(f"遇到服务器内部错误(500)，{retry_wait}秒后将重试...")
                                await asyncio.sleep(retry_wait)
                                pages_fetched -= 1  # 重试同一页
                                continue
                                
                            break

                except asyncio.TimeoutError:
                    raise
                except aiohttp.ClientError:
                    raise

            self.logger.info(f"用户 {user_id} 总共获取 {len(all_tweets)} 条推文")
            return all_tweets

        except Exception as e:
            self.logger.error(f"获取用户 {user_id} 推文时发生未预期错误: {e}")
            return []

    @retry_on_error(max_retries=3, backoff_factor=1.0)
    async def get_tweet_comments(self, tweet_id: str, conversation_id: str, max_comments: int, session: aiohttp.ClientSession) -> List[Dict]:
        """获取推文评论"""
        all_comments = []
        comments_start_time = time.time()
        
        if not conversation_id:
            self.logger.warning(f"推文 {tweet_id} 没有 conversation_id，无法获取评论")
            return all_comments
            
        # 性能优化：跳过超大评论数量的推文（通常是热门推文，爬取非常耗时）
        reply_count = 0
        try:
            reply_count = self.kol_tweets_cursor.execute(
                "SELECT replies_count FROM tweets WHERE tweet_id = ?", (tweet_id,)
            ).fetchone()[0]
            
            # 如果回复数超过1000，则限制最大获取数为300条
            if reply_count > 1000:
                original_max = max_comments if max_comments > 0 else "全部"
                self.logger.info(f"推文 {tweet_id} 有 {reply_count} 条回复，原定获取 {original_max}，限制为最多300条")
                max_comments = min(max_comments, 300) if max_comments > 0 else 300
        except Exception:
            pass
            
        try:
            url = f"{self.base_url}/search-tweets"
            query = f"conversation_id:{conversation_id}"
            next_cursor = ""
            # 确保有足够的页数获取到我们需要的评论数
            max_comment_pages = (max_comments // 20) + 3 if max_comments > 0 else 20  # 调整页数计算
            
            for page in range(max_comment_pages):
                page_start_time = time.time()
                data = {
                    "query": query,
                    "next_cursor": next_cursor
                }
                
                try:
                    # 使用评论限速器控制请求速率
                    await self.comment_rate_limiter.acquire()
                    
                    api_call_start = time.time()
                    async with session.post(url, headers=self.headers, json=data, timeout=120) as response:
                        api_call_end = time.time()
                        api_duration = api_call_end - api_call_start
                        
                        if response.status == 200:
                            parse_start = time.time()
                            response_text = await response.text()
                            if not response_text.strip():
                                self.logger.warning(f"API 返回空响应，查询: {query}, 页: {page+1}")
                                break
                                
                            try:
                                response_data = json.loads(response_text)
                            except json.JSONDecodeError:
                                self.logger.error(f"API 返回无效 JSON，查询: {query}, 页: {page+1}. 响应: {response_text[:200]}...")
                                break
                            
                            parse_end = time.time()
                            parse_duration = parse_end - parse_start
                            
                            comments = response_data.get("tweets", [])
                            if not comments:
                                self.logger.debug(f"对话 {conversation_id} 第 {page+1} 页没有更多评论")
                                break
                                
                            # 过滤掉原始推文
                            filter_start = time.time()
                            filtered_comments = [
                                c for c in comments
                                if c.get("id_str") != tweet_id and c.get("conversation_id_str") == conversation_id
                            ]
                            filter_end = time.time()
                            
                            all_comments.extend(filtered_comments)
                            self.logger.debug(f"推文 {tweet_id} 第 {page+1} 页获取 {len(filtered_comments)} 条评论 (总计: {len(all_comments)}) "
                                              f"[API: {api_duration:.2f}s, 解析: {parse_duration:.2f}s, 过滤: {filter_end-filter_start:.2f}s]")
                            
                            if max_comments > 0 and len(all_comments) >= max_comments:
                                all_comments = all_comments[:max_comments]
                                self.logger.debug(f"推文 {tweet_id} 达到最大评论数 ({max_comments})")
                                break
                            
                            next_cursor = response_data.get("next_cursor")
                            if not next_cursor:
                                self.logger.debug(f"对话 {conversation_id} 没有下一页，结束评论获取")
                                break
                            
                            page_end_time = time.time()
                            self.logger.debug(f"推文 {tweet_id} 评论页 {page+1} 处理完成，耗时: {page_end_time - page_start_time:.2f}秒")
                            
                            # 页面间不需要额外延迟，限速器已经控制了请求速率
                            
                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 60))
                            self.logger.warning(f"获取推文 {tweet_id} 评论第 {page+1} 页时被限速 (429)。等待 {retry_after} 秒...")
                            # 遇到429时，调整限速器的速率，但降低幅度更小
                            self.comment_rate_limiter.requests_per_second *= 0.9  # 降低10%的请求速率
                            self.comment_rate_limiter.min_interval = 1.0 / self.comment_rate_limiter.requests_per_second
                            self.logger.info(f"轻微调整评论请求速率为每秒 {self.comment_rate_limiter.requests_per_second:.2f} 请求")
                            await asyncio.sleep(retry_after)
                            continue
                            
                        else:
                            error_text = await response.text()
                            self.logger.error(f"获取推文 {tweet_id} 评论第 {page+1} 页时 API 错误: 状态 {response.status}, {error_text[:200]}...")
                            
                            # 对500错误进行重试处理
                            if response.status == 500:
                                retry_wait = 5  # 等待5秒后重试
                                self.logger.warning(f"遇到服务器内部错误(500)，{retry_wait}秒后将重试...")
                                await asyncio.sleep(retry_wait)
                                page -= 1  # 重试同一页 - 修正这里使用正确的变量名page而不是pages_fetched
                                continue
                                
                            break
                            
                except asyncio.TimeoutError:
                    raise
                except aiohttp.ClientError:
                    raise
            
            comments_end_time = time.time()
            self.logger.info(f"推文 {tweet_id} 总共获取 {len(all_comments)} 条评论，总耗时: {comments_end_time - comments_start_time:.2f}秒")
            return all_comments
            
        except Exception as e:
            self.logger.error(f"获取推文 {tweet_id} 评论时发生未预期错误: {e}")
            return []

    def save_tweet(self, user_info: Dict, tweet_data: Dict):
        """保存推文到数据库"""
        if not self.kol_tweets_conn or not self.kol_tweets_cursor:
            self.logger.error("数据库连接不可用，无法保存推文")
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

            self.kol_tweets_cursor.execute('''
                INSERT OR REPLACE INTO tweets
                (tweet_id, conversation_id, author_id, author_name, full_text, created_at,
                 likes_count, retweets_count, replies_count, views_count, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                tweet_data.get('id_str'),
                tweet_data.get('conversation_id_str'),
                user_info['user_id'],
                user_info['username'],
                tweet_data.get('full_text', ''),
                created_at_dt,
                tweet_data.get('favorite_count', 0),
                tweet_data.get('retweet_count', 0),
                tweet_data.get('reply_count', 0),
                tweet_data.get('view_count', 0)
            ))
            
            # 性能优化：批量提交
            self.tweet_batch_counter += 1
            if self.tweet_batch_counter >= self.batch_size:
                self.kol_tweets_conn.commit()
                self.tweet_batch_counter = 0
            
        except sqlite3.Error as e:
            self.logger.error(f"保存推文时发生数据库错误: {e}")
        except Exception as e:
            self.logger.error(f"保存推文时发生未预期错误: {e}")

    def save_comments_batch(self, tweet_id: str, comments_data: List[Dict]):
        """批量保存评论到数据库"""
        if not self.kol_tweets_conn or not self.kol_tweets_cursor:
            self.logger.error("数据库连接不可用，无法保存评论")
            return
            
        if not comments_data:
            return
            
        try:
            batch_start = time.time()
            values = []
            
            for comment_data in comments_data:
                created_at_dt = None
                created_at_str = comment_data.get('created_at')
                if created_at_str:
                    try:
                        created_at_dt = parsedate_to_datetime(created_at_str)
                        if created_at_dt.tzinfo:
                            created_at_dt = created_at_dt.replace(tzinfo=None)
                    except Exception:
                        pass
                        
                user_info = comment_data.get('user', {})
                values.append((
                    tweet_id,
                    comment_data.get('id_str'),
                    user_info.get('id_str'),
                    user_info.get('screen_name'),
                    comment_data.get('full_text', ''),
                    created_at_dt,
                    comment_data.get('favorite_count', 0)
                ))
            
            # 批量插入
            self.kol_tweets_cursor.executemany('''
                INSERT OR IGNORE INTO comments
                (tweet_id, comment_id, author_id, author_name, comment_text, created_at, likes_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', values)
            
            # 每批次评论直接提交
            self.kol_tweets_conn.commit()
            
            batch_end = time.time()
            self.logger.debug(f"批量保存 {len(comments_data)} 条评论，耗时: {batch_end - batch_start:.2f}秒")
            
        except sqlite3.Error as e:
            self.logger.error(f"批量保存评论时发生数据库错误: {e}")
        except Exception as e:
            self.logger.error(f"批量保存评论时发生未预期错误: {e}")

    def save_comment(self, tweet_id: str, comment_data: Dict):
        """保存评论到数据库"""
        if not self.kol_tweets_conn or not self.kol_tweets_cursor:
            self.logger.error("数据库连接不可用，无法保存评论")
            return
            
        try:
            created_at_dt = None
            created_at_str = comment_data.get('created_at')
            if created_at_str:
                try:
                    created_at_dt = parsedate_to_datetime(created_at_str)
                    if created_at_dt.tzinfo:
                        created_at_dt = created_at_dt.replace(tzinfo=None)
                except Exception:
                    self.logger.warning(f"无法解析评论日期: {created_at_str}")
                    
            user_info = comment_data.get('user', {})
            self.kol_tweets_cursor.execute('''
                INSERT OR IGNORE INTO comments
                (tweet_id, comment_id, author_id, author_name, comment_text, created_at, likes_count, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                tweet_id,
                comment_data.get('id_str'),
                user_info.get('id_str'),
                user_info.get('screen_name'),
                comment_data.get('full_text', ''),
                created_at_dt,
                comment_data.get('favorite_count', 0)
            ))
            
            # 性能优化：批量提交
            self.comment_batch_counter += 1
            if self.comment_batch_counter >= self.batch_size:
                self.kol_tweets_conn.commit()
                self.comment_batch_counter = 0
            
        except sqlite3.Error as e:
            self.logger.error(f"保存评论时发生数据库错误: {e}")
        except Exception as e:
            self.logger.error(f"保存评论时发生未预期错误: {e}")

    def update_processing_log(self, user_info: Dict, tweets_count: int, comments_count: int, status: str):
        """更新用户处理记录"""
        try:
            self.kol_tweets_cursor.execute('''
                INSERT OR REPLACE INTO processing_log
                (user_id, username, tweets_collected, comments_collected, last_processed, status)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            ''', (
                user_info.get('user_id'),
                user_info.get('username'),
                tweets_count,
                comments_count,
                status
            ))
        except sqlite3.Error as e:
            self.logger.error(f"更新处理记录时发生数据库错误: {e}")

    async def process_user(self, user_info: Dict, max_tweets: int, max_comments_per_tweet: int, 
                          collect_comments: bool, tweet_semaphore: asyncio.Semaphore, 
                          comment_semaphore: asyncio.Semaphore, session: aiohttp.ClientSession):
        """处理单个用户的推文和评论"""
        user_id = user_info.get('user_id')
        username = user_info.get('username', 'N/A')
        
        if not user_id:
            self.logger.warning(f"跳过用户，缺少 user_id: {user_info}")
            return
            
        async with tweet_semaphore:  # 使用推文并发控制
            user_start_time = time.time()
            self.logger.info(f"开始处理用户: {username} ({user_id}) [粉丝数: {user_info.get('followers_count', 'N/A')}]")
            tweets_collected = 0
            comments_collected = 0
            
            try:
                # 1. 获取用户推文
                tweets_start_time = time.time()
                tweets = await self.get_user_tweets(user_id, max_tweets, session)
                tweets_end_time = time.time()
                
                if tweets:
                    self.logger.info(f"用户 {username} 获取到 {len(tweets)} 条推文，耗时: {tweets_end_time - tweets_start_time:.2f}秒，开始处理...")
                    
                    # 性能优化：优先处理有评论的推文
                    if collect_comments:
                        # 按回复数量排序，从多到少
                        tweets = sorted(tweets, key=lambda t: t.get('reply_count', 0), reverse=True)
                    
                    # 异步处理评论任务
                    comments_tasks = []
                    
                    for i, tweet in enumerate(tweets):
                        tweet_process_start = time.time()
                        # 保存推文
                        self.save_tweet(user_info, tweet)
                        tweets_collected += 1
                        
                        # 2. 如果需要收集评论且推文有回复
                        if collect_comments and tweet.get('reply_count', 0) > 0:
                            tweet_id = tweet.get('id_str')
                            conversation_id = tweet.get('conversation_id_str')
                            
                            if tweet_id and conversation_id:
                                # 创建评论获取任务，不立即等待
                                task = asyncio.create_task(self._get_and_save_comments(
                                    tweet_id, conversation_id, max_comments_per_tweet, 
                                    comment_semaphore, session
                                ))
                                comments_tasks.append(task)
                        
                        tweet_process_end = time.time()
                        self.logger.debug(f"处理推文 [{i+1}/{len(tweets)}] ID: {tweet.get('id_str')} 完成，耗时: {tweet_process_end - tweet_process_start:.2f}秒")
                    
                    # 等待所有评论获取任务完成
                    if comments_tasks:
                        self.logger.info(f"用户 {username} 正在等待 {len(comments_tasks)} 个评论获取任务完成...")
                        comments_results = await asyncio.gather(*comments_tasks, return_exceptions=True)
                        
                        # 统计结果
                        for result in comments_results:
                            if isinstance(result, tuple) and len(result) == 2:
                                comments_count, _ = result
                                comments_collected += comments_count
                            elif isinstance(result, Exception):
                                self.logger.error(f"评论获取任务出错: {result}")
                
                # 提交用户的所有数据
                if self.kol_tweets_conn:
                    self.kol_tweets_conn.commit()
                    
                # 更新处理记录
                self.update_processing_log(user_info, tweets_collected, comments_collected, 'completed')
                if self.kol_tweets_conn:
                    self.kol_tweets_conn.commit()
                    
            except Exception as e:
                self.logger.error(f"处理用户 {username} ({user_id}) 时发生错误: {e}")
                self.logger.error(traceback.format_exc())
                
                # 错误时回滚并记录
                if self.kol_tweets_conn:
                    self.kol_tweets_conn.rollback()
                self.update_processing_log(user_info, tweets_collected, comments_collected, 'error')
                if self.kol_tweets_conn:
                    self.kol_tweets_conn.commit()
                    
            finally:
                user_end_time = time.time()
                self.logger.info(f"完成处理用户 {username}。收集推文: {tweets_collected}，评论: {comments_collected}，总耗时: {user_end_time - user_start_time:.2f}秒")
                
    async def _get_and_save_comments(self, tweet_id: str, conversation_id: str, 
                                    max_comments: int, comment_semaphore: asyncio.Semaphore, 
                                    session: aiohttp.ClientSession):
        """获取并保存评论的辅助方法"""
        comments_count = 0
        task_start = time.time()
        
        async with comment_semaphore:
            try:
                comments = await self.get_tweet_comments(
                    tweet_id, conversation_id, max_comments, session
                )
                
                if comments:
                    self.save_comments_batch(tweet_id, comments)
                    comments_count = len(comments)
            except Exception as e:
                self.logger.error(f"处理推文 {tweet_id} 评论时出错: {e}")
                
        task_end = time.time()
        return comments_count, task_end - task_start

    async def run(self, max_tweets: int = 100, max_comments_per_tweet: int = 50, 
                 collect_comments: bool = True, max_tweet_tasks: int = 25, max_comment_tasks: int = 20):
        """运行完整的 KOL 爬虫"""
        run_start_time = time.time()
        self.logger.info(f"--- 开始 KOL 完整爬虫 ---")
        self.logger.info(f"参数: 最大推文数={max_tweets}, 每推文最大评论数={max_comments_per_tweet}, 收集评论={collect_comments}, 推文并发数={max_tweet_tasks}, 评论并发数={max_comment_tasks}")
        
        try:
            # 1. 加载所有 KOL 用户
            users = self.load_kol_users()
            if not users:
                self.logger.warning("没有找到用户，终止爬取")
                return
                
            # 2. 处理所有用户
            tweet_semaphore = asyncio.Semaphore(max_tweet_tasks)
            comment_semaphore = asyncio.Semaphore(max_comment_tasks)
            self.logger.info(f"开始处理 {len(users)} 个用户...")
            
            async with aiohttp.ClientSession() as session:
                tasks = []
                for user_info in users:
                    task = asyncio.create_task(self.process_user(
                        user_info, max_tweets, max_comments_per_tweet, 
                        collect_comments, tweet_semaphore, comment_semaphore, session
                    ))
                    tasks.append(task)
                    
                if tasks:
                    # 处理所有任务
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # 统计结果
                    success_count = 0
                    error_count = 0
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            error_count += 1
                            user_info = users[i]
                            self.logger.error(f"用户 {user_info.get('username')} 处理任务出错: {result}")
                        else:
                            success_count += 1
                            
                    self.logger.info(f"所有用户处理完成。成功: {success_count}, 失败: {error_count}")
                else:
                    self.logger.info("没有安排用户处理任务")
                    
        except Exception as e:
            self.logger.error(f"KOL 完整爬虫运行期间发生错误: {e}")
            self.logger.error(traceback.format_exc())
            
        finally:
            # 不在这里关闭连接，而是在main函数中关闭
            run_end_time = time.time()
            self.logger.info(f"--- KOL 完整爬虫结束 (耗时: {run_end_time - run_start_time:.2f} 秒) ---")

    def get_statistics(self):
        """获取爬取统计信息"""
        connection_created = False
        try:
            # 如果连接不可用，创建新的连接
            if not self.kol_tweets_conn:
                self.logger.info("为统计信息创建新的数据库连接")
                connection_created = True
                self.kol_tweets_conn = sqlite3.connect(
                    self.kol_tweets_db_path, 
                    detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES, 
                    timeout=10
                )
                
            cursor = self.kol_tweets_conn.cursor()
            
            # 推文统计
            cursor.execute("SELECT COUNT(*) FROM tweets")
            total_tweets = cursor.fetchone()[0]
            
            # 评论统计
            cursor.execute("SELECT COUNT(*) FROM comments")
            total_comments = cursor.fetchone()[0]
            
            # 用户统计
            cursor.execute("SELECT COUNT(*) FROM processing_log")
            total_users_processed = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM processing_log WHERE status = 'completed'")
            successful_users = cursor.fetchone()[0]
            
            # 按用户统计
            cursor.execute("""
                SELECT username, tweets_collected, comments_collected, status, last_processed
                FROM processing_log
                ORDER BY tweets_collected DESC
                LIMIT 10
            """)
            top_users = cursor.fetchall()
            
            print("\n" + "="*50)
            print("KOL 爬虫统计信息")
            print("="*50)
            print(f"总推文数: {total_tweets}")
            print(f"总评论数: {total_comments}")
            print(f"处理用户数: {total_users_processed}")
            print(f"成功用户数: {successful_users}")
            print(f"成功率: {successful_users/total_users_processed*100:.1f}%" if total_users_processed > 0 else "N/A")
            
            print("\n前10名用户(按推文数):")
            print("-"*70)
            print(f"{'用户名':<20} {'推文数':<10} {'评论数':<10} {'状态':<10} {'处理时间':<20}")
            print("-"*70)
            for user in top_users:
                print(f"{user[0]:<20} {user[1]:<10} {user[2]:<10} {user[3]:<10} {user[4]:<20}")
            print("="*50)
            
        except sqlite3.Error as e:
            self.logger.error(f"获取统计信息时发生数据库错误: {e}")
        except Exception as e:
            self.logger.error(f"获取统计信息时发生未预期错误: {e}")
        finally:
            # 如果是我们创建的连接，关闭它
            if connection_created and self.kol_tweets_conn:
                self.logger.info("关闭统计信息的数据库连接")
                self.kol_tweets_conn.close()
                self.kol_tweets_conn = None


async def main():
    parser = argparse.ArgumentParser(description="KOL 完整爬虫 - 爬取推文和评论")
    parser.add_argument("--kol_db_path", type=str, required=True, help="KOL_yes.db 文件的完整路径")
    parser.add_argument("--api_key", type=str, default="请输入你的api", help="TweetScout API 密钥")
    parser.add_argument("--max_tweets", type=int, default=100, help="每用户最大推文数 (0=全部)")
    parser.add_argument("--max_comments_per_tweet", type=int, default=50, help="每推文最大评论数 (0=全部)")
    parser.add_argument("--collect_comments", action="store_true", default=True, help="是否收集评论")
    parser.add_argument("--no_comments", action="store_true", help="不收集评论")
    parser.add_argument("--max_tweet_tasks", type=int, default=25, help="推文爬取并发任务数")
    parser.add_argument("--max_comment_tasks", type=int, default=20, help="评论爬取并发任务数")
    parser.add_argument("--stats_only", action="store_true", help="仅显示统计信息")
    
    args = parser.parse_args()
    
    # 处理评论收集参数
    collect_comments = args.collect_comments and not args.no_comments
    
    print(f"KOL 完整爬虫")
    print(f"KOL数据库路径: {args.kol_db_path}")
    print(f"输出目录: {os.path.dirname(args.kol_db_path)}")
    print(f"最大推文数: {'全部' if args.max_tweets == 0 else args.max_tweets}")
    print(f"每推文最大评论数: {'全部' if args.max_comments_per_tweet == 0 else args.max_comments_per_tweet}")
    print(f"收集评论: {'是' if collect_comments else '否'}")
    print(f"推文爬取并发数: {args.max_tweet_tasks}")
    print(f"评论爬取并发数: {args.max_comment_tasks}")
    
    # 从环境变量加载 API 密钥
    api_key = os.getenv("TWEETSCOUT_API_KEY", args.api_key)
    if api_key == "你的api秘钥":
        print("警告: 使用默认 API 密钥")
        
    crawler = KOLCompleteCrawler(
        api_key=api_key,
        kol_db_path=args.kol_db_path
    )
    
    try:
        if args.stats_only:
            # 仅显示统计信息
            crawler.get_statistics()
        else:
            # 运行爬虫
            await crawler.run(
                max_tweets=args.max_tweets,
                max_comments_per_tweet=args.max_comments_per_tweet,
                collect_comments=collect_comments,
                max_tweet_tasks=args.max_tweet_tasks,
                max_comment_tasks=args.max_comment_tasks
            )
            
            # 显示最终统计 - 在运行结束后但在关闭连接前显示统计
            crawler.get_statistics()
    finally:
        # 确保手动关闭连接
        if hasattr(crawler, '_close_connections'):
            crawler._close_connections()

if __name__ == "__main__":
    asyncio.run(main())