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

class KOLCommentCrawler:
    def __init__(self, api_key: str, db_dir: str):
        self.api_key = api_key
        self.base_url = "https://api.tweetscout.io/v2"
        self.db_dir = db_dir
        
        # 数据库路径
        self.tweets_db_path = os.path.join(self.db_dir, "tweets.db")
        self.tweets_a_db_path = os.path.join(self.db_dir, "tweetsA.db")
        self.kol_yes_db_path = os.path.join(self.db_dir, "KOL_yes.db")
        
        self.headers = {
            "ApiKey": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        self._setup_logging()
        self.tweets_conn = None
        self.tweets_a_conn = None
        self.kol_yes_conn = None
        
        # 初始化数据库连接
        self._init_databases()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s'
        )
        self.logger = logging.getLogger("KOLCommentCrawler")

    def _init_databases(self):
        """初始化数据库连接和创建必要的表"""
        try:
            # 确保目录存在
            os.makedirs(self.db_dir, exist_ok=True)
            
            # 连接 tweets.db (只读)
            self.tweets_conn = sqlite3.connect(self.tweets_db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES, timeout=10)
            self.tweets_conn.execute("PRAGMA query_only = ON;")  # 只读模式
            
            # 连接 KOL_yes.db (只读)
            self.kol_yes_conn = sqlite3.connect(self.kol_yes_db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES, timeout=10)
            self.kol_yes_conn.execute("PRAGMA query_only = ON;")  # 只读模式
            
            # 连接/创建 tweetsA.db
            self.tweets_a_conn = sqlite3.connect(self.tweets_a_db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES, timeout=10)
            self.tweets_a_cursor = self.tweets_a_conn.cursor()
            self.tweets_a_conn.execute("PRAGMA journal_mode=WAL;")  # 提高并发性
            self.tweets_a_conn.execute("PRAGMA busy_timeout = 5000;")  # 锁定时等待5秒
            
            # 在 tweetsA.db 中创建与 tweets.db 相同的表结构
            self.tweets_a_cursor.execute('''
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
            self.tweets_a_cursor.execute('''
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
            
            # 创建索引
            self.tweets_a_cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_author_id ON tweets(author_id)')
            self.tweets_a_cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_created_at ON tweets(created_at)')
            self.tweets_a_cursor.execute('CREATE INDEX IF NOT EXISTS idx_comment_tweet_id ON comments(tweet_id)')
            
            self.tweets_a_conn.commit()
            self.logger.info(f"所有数据库连接初始化完成")
            
        except sqlite3.Error as e:
            self.logger.error(f"数据库初始化失败: {e}")
            self._close_connections()
        except Exception as e:
            self.logger.error(f"初始化过程中发生未预期错误: {e}")
            self._close_connections()

    def _close_connections(self):
        """关闭所有数据库连接"""
        try:
            if self.tweets_conn:
                self.tweets_conn.close()
                self.tweets_conn = None
            if self.kol_yes_conn:
                self.kol_yes_conn.close()
                self.kol_yes_conn = None
            if self.tweets_a_conn:
                self.tweets_a_conn.close()
                self.tweets_a_conn = None
                self.tweets_a_cursor = None
            self.logger.info("所有数据库连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭数据库连接时发生错误: {e}")

    def get_kol_user_ids(self) -> List[str]:
        """从 KOL_yes.db 获取所有 KOL 用户的 user_id"""
        kol_user_ids = []
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
                
            # 获取所有 KOL 用户的 user_id
            cursor.execute("SELECT user_id FROM users WHERE user_id IS NOT NULL AND user_id != ''")
            rows = cursor.fetchall()
            
            kol_user_ids = [row[0] for row in rows]
            self.logger.info(f"从 KOL_yes.db 中获取到 {len(kol_user_ids)} 个 KOL 用户")
            
            return kol_user_ids
            
        except sqlite3.Error as e:
            self.logger.error(f"获取 KOL 用户 ID 时发生数据库错误: {e}")
            return []
        except Exception as e:
            self.logger.error(f"获取 KOL 用户 ID 时发生未预期错误: {e}")
            return []

    def copy_kol_tweets_to_tweetsA(self, kol_user_ids: List[str]):
        """将 KOL 用户的推文从 tweets.db 复制到 tweetsA.db"""
        if not kol_user_ids:
            self.logger.warning("没有 KOL 用户 ID，跳过复制推文")
            return
            
        try:
            if not self.tweets_conn or not self.tweets_a_conn:
                self.logger.error("数据库连接不可用，无法复制推文")
                return
                
            tweets_cursor = self.tweets_conn.cursor()
            
            # 分批处理，每批最多50个用户ID
            batch_size = 50
            total_copied = 0
            
            for i in range(0, len(kol_user_ids), batch_size):
                batch = kol_user_ids[i:i+batch_size]
                # 创建参数占位符
                placeholders = ','.join(['?' for _ in batch])
                
                # 查询并复制推文
                query = f"SELECT * FROM tweets WHERE author_id IN ({placeholders})"
                tweets_cursor.execute(query, batch)
                tweets = tweets_cursor.fetchall()
                
                if tweets:
                    # 获取列名
                    columns = [desc[0] for desc in tweets_cursor.description]
                    # 构建插入语句
                    insert_placeholders = ','.join(['?' for _ in columns])
                    insert_query = f"INSERT OR IGNORE INTO tweets ({','.join(columns)}) VALUES ({insert_placeholders})"
                    
                    # 批量插入
                    self.tweets_a_cursor.executemany(insert_query, tweets)
                    self.tweets_a_conn.commit()
                    
                    batch_copied = len(tweets)
                    total_copied += batch_copied
                    self.logger.info(f"已复制 {batch_copied} 条推文 (批次 {i//batch_size + 1}, 累计 {total_copied})")
            
            self.logger.info(f"总共将 {total_copied} 条 KOL 用户推文从 tweets.db 复制到 tweetsA.db")
            
        except sqlite3.Error as e:
            self.logger.error(f"复制推文时发生数据库错误: {e}")
            if self.tweets_a_conn:
                self.tweets_a_conn.rollback()
        except Exception as e:
            self.logger.error(f"复制推文时发生未预期错误: {e}")
            if self.tweets_a_conn:
                self.tweets_a_conn.rollback()

    def get_tweets_to_process(self) -> List[Dict]:
        """从 tweetsA.db 获取需要爬取评论的推文信息"""
        tweets_to_process = []
        try:
            if not self.tweets_a_conn:
                self.logger.error("tweetsA.db 连接不可用")
                return []
                
            cursor = self.tweets_a_conn.cursor()
            
            # 查询有回复的推文
            cursor.execute("""
                SELECT tweet_id, conversation_id, author_id, author_name, replies_count 
                FROM tweets 
                WHERE conversation_id IS NOT NULL 
                AND replies_count > 0
                ORDER BY replies_count DESC
            """)
            
            rows = cursor.fetchall()
            
            for row in rows:
                tweets_to_process.append({
                    "tweet_id": row[0],
                    "conversation_id": row[1],
                    "author_id": row[2],
                    "author_name": row[3],
                    "replies_count": row[4]
                })
                
            self.logger.info(f"从 tweetsA.db 中获取到 {len(tweets_to_process)} 条需要爬取评论的推文")
            return tweets_to_process
            
        except sqlite3.Error as e:
            self.logger.error(f"获取待处理推文时发生数据库错误: {e}")
            return []
        except Exception as e:
            self.logger.error(f"获取待处理推文时发生未预期错误: {e}")
            return []

    @retry_on_error(max_retries=3, backoff_factor=1.0)
    async def get_tweet_comments(self, tweet_id: str, conversation_id: str, session: aiohttp.ClientSession) -> List[Dict]:
        """获取推文的评论"""
        all_comments = []
        if not conversation_id:
            self.logger.warning(f"推文 {tweet_id} 没有提供 conversation_id，无法获取评论")
            return all_comments
            
        try:
            url = f"{self.base_url}/search-tweets"
            query = f"conversation_id:{conversation_id}"
            next_cursor = ""
            max_comment_pages = 5  # 限制页数，防止热门推文过度调用
            
            for page in range(max_comment_pages):
                data = {
                    "query": query,
                    "next_cursor": next_cursor
                }
                
                try:
                    async with session.post(url, headers=self.headers, json=data, timeout=120) as response:
                        if response.status == 200:
                            response_text = await response.text()
                            if not response_text.strip():
                                self.logger.warning(f"API 返回空响应，查询: {query}, 页: {page+1}")
                                break
                                
                            try:
                                response_data = json.loads(response_text)
                            except json.JSONDecodeError:
                                self.logger.error(f"API 返回无效 JSON，查询: {query}, 页: {page+1}. 响应: {response_text[:200]}...")
                                break
                                
                            comments = response_data.get("tweets", [])
                            if not comments:
                                self.logger.debug(f"对话 {conversation_id} 没有更多评论, 页: {page+1}")
                                break
                                
                            # 过滤掉原始推文，确保它是对话的一部分
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
                                
                            await asyncio.sleep(2)  # 页面间限速
                            
                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 60))
                            self.logger.warning(f"获取推文 {tweet_id} 的评论页 {page+1} 时被限速 (429)。等待 {retry_after} 秒...")
                            await asyncio.sleep(retry_after)
                            continue  # 重试同一页
                            
                        else:
                            error_text = await response.text()
                            self.logger.error(f"获取推文 {tweet_id} 的评论页 {page+1} 时 API 错误: 状态 {response.status}, {error_text[:200]}...")
                            break  # 错误时停止获取该推文的评论
                            
                except asyncio.TimeoutError:
                    raise  # 让装饰器处理重试
                except aiohttp.ClientError:
                    raise  # 让装饰器处理重试
                    
                # 如果达到最大页数限制，则中断
                if page == max_comment_pages - 1 and next_cursor:
                    self.logger.warning(f"推文 {tweet_id} 达到最大评论页数限制 ({max_comment_pages})")
                    
            self.logger.debug(f"完成获取推文 {tweet_id} 的评论。总共找到: {len(all_comments)}")
            return all_comments
            
        except Exception as e:
            self.logger.error(f"搜索推文 {tweet_id} 的评论时发生未预期错误: {e}")
            self.logger.error(traceback.format_exc())
            return []

    def save_comment(self, tweet_id: str, comment_data: Dict):
        """将评论保存到 tweetsA.db"""
        if not self.tweets_a_conn or not self.tweets_a_cursor:
            self.logger.error("数据库连接不可用，无法保存评论")
            return
            
        try:
            created_at_dt = None
            created_at_str = comment_data.get('created_at')
            if created_at_str:
                try:
                    # 确保一致的 UTC 时区 (如果可能)，否则使用无时区的日期时间
                    created_at_dt = parsedate_to_datetime(created_at_str)
                    # 如果有时区信息但为了一致性存储需要去掉
                    if created_at_dt.tzinfo:
                        created_at_dt = created_at_dt.replace(tzinfo=None)
                except Exception:
                    self.logger.warning(f"无法解析评论日期: {created_at_str}")
                    
            self.tweets_a_cursor.execute('''
                INSERT OR IGNORE INTO comments
                (tweet_id, comment_id, author_id, comment_text, created_at, likes_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                tweet_id,
                comment_data.get('id_str'),
                comment_data.get('user', {}).get('id_str'),
                comment_data.get('full_text', ''),
                created_at_dt,  # 存储日期时间对象
                comment_data.get('favorite_count', 0)
            ))
            # 提交在处理推文时处理，以提高效率
            
        except sqlite3.Error as e:
            self.logger.error(f"保存推文 {tweet_id} 的评论时发生数据库错误: {e}")
        except Exception as e:
            self.logger.error(f"保存评论时发生未预期错误: {e}")

    async def process_tweet(self, tweet_info: Dict, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession):
        """处理单个推文的评论"""
        tweet_id = tweet_info.get('tweet_id')
        conversation_id = tweet_info.get('conversation_id')
        author_name = tweet_info.get('author_name', 'N/A')
        
        if not tweet_id or not conversation_id:
            self.logger.warning(f"跳过推文，因为缺少 tweet_id 或 conversation_id: {tweet_info}")
            return
            
        async with semaphore:
            self.logger.info(f"开始处理作者 {author_name} 的推文 {tweet_id} 的评论")
            processed_comments = 0
            
            try:
                # 获取评论
                comments = await self.get_tweet_comments(tweet_id, conversation_id, session)
                
                if comments:
                    self.logger.info(f"为推文 {tweet_id} 获取到 {len(comments)} 条评论，开始保存")
                    
                    for comment in comments:
                        self.save_comment(tweet_id, comment)
                        processed_comments += 1
                        
                    # 提交事务
                    if self.tweets_a_conn:
                        self.tweets_a_conn.commit()
                        
                else:
                    self.logger.info(f"推文 {tweet_id} 没有找到评论")
                    
            except Exception as e:
                self.logger.error(f"处理推文 {tweet_id} 的评论时发生错误: {e}")
                self.logger.error(traceback.format_exc())
                # 错误时回滚
                if self.tweets_a_conn:
                    self.tweets_a_conn.rollback()
                    
            finally:
                self.logger.info(f"完成处理推文 {tweet_id}。保存了 {processed_comments} 条评论。")

    async def run(self, max_concurrent_tasks: int = 5):
        """运行 KOL 评论爬虫"""
        run_start_time = time.time()
        self.logger.info(f"--- 开始 KOL 评论收集 (并发: {max_concurrent_tasks}) ---")
        
        try:
            # 1. 获取 KOL 用户 ID
            kol_user_ids = self.get_kol_user_ids()
            if not kol_user_ids:
                self.logger.warning("没有找到 KOL 用户，终止评论收集")
                return
                
            # 2. 将 KOL 推文从 tweets.db 复制到 tweetsA.db
            self.copy_kol_tweets_to_tweetsA(kol_user_ids)
            
            # 3. 获取需要处理的推文
            tweets_to_process = self.get_tweets_to_process()
            if not tweets_to_process:
                self.logger.warning("没有需要处理的推文，终止评论收集")
                return
                
            # 4. 处理推文评论
            semaphore = asyncio.Semaphore(max_concurrent_tasks)
            self.logger.info(f"开始处理 {len(tweets_to_process)} 条推文的评论...")
            
            async with aiohttp.ClientSession() as session:
                tasks = []
                for tweet_info in tweets_to_process:
                    task = asyncio.create_task(self.process_tweet(tweet_info, semaphore, session))
                    tasks.append(task)
                    
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            tweet_info = tweets_to_process[i]
                            self.logger.error(f"处理推文 {tweet_info.get('tweet_id')} 的任务出错: {result}")
                    self.logger.info("所有推文评论处理任务已完成（或失败）")
                else:
                    self.logger.info("没有安排推文处理任务")
                    
        except Exception as e:
            self.logger.error(f"KOL 评论爬虫运行期间发生错误: {e}")
            self.logger.error(traceback.format_exc())
            
        finally:
            self._close_connections()
            run_end_time = time.time()
            self.logger.info(f"--- KOL 评论收集结束 (耗时: {run_end_time - run_start_time:.2f} 秒) ---")

async def main():
    parser = argparse.ArgumentParser(description="KOL 评论爬虫")
    parser.add_argument("--db_dir", type=str, required=True, help="包含数据库的目录")
    parser.add_argument("--api_key", type=str, default="你的api", help="TweetScout API 密钥")
    parser.add_argument("--max_concurrent_tasks", type=int, default=5, help="并发任务数")
    args = parser.parse_args()
    
    print(f"使用 db_dir: {args.db_dir} 运行 KOL 评论爬虫")
    
    # 从环境变量加载 API 密钥（如果可能）
    api_key = os.getenv("TWEETSCOUT_API_KEY", args.api_key)
    if api_key == "你的api":
        print("警告: 使用默认 API 密钥")
        
    crawler = KOLCommentCrawler(
        api_key=api_key,
        db_dir=args.db_dir
    )
    
    await crawler.run(max_concurrent_tasks=args.max_concurrent_tasks)

if __name__ == "__main__":
    asyncio.run(main()) 