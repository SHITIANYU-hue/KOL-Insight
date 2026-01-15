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

class TweetCrawler:
    # 修改构造函数，增加 db_dir 参数
    def __init__(self, api_key: str, db_dir: str):
        self.api_key = api_key
        self.base_url = "https://api.tweetscout.io/v2"
        self.db_dir = db_dir
        self.tweets_db_path = os.path.join(self.db_dir, "tweets.db")
        self.following_db_path = os.path.join(self.db_dir, "followingA.db")
        self.headers = {
            "ApiKey": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self._setup_logging()
        self.conn = None
        self.cursor = None
        self._init_database()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s'
        )
        self.logger = logging.getLogger("TweetCrawler")

    def _init_database(self):
        """初始化用于存储推文和评论的数据库 (tweets.db)"""
        try:
            # Ensure the directory exists before connecting
            os.makedirs(self.db_dir, exist_ok=True)
            # Connect to tweets.db using the constructed path
            self.conn = sqlite3.connect(self.tweets_db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES, timeout=10) # Add timeout
            self.cursor = self.conn.cursor()
            self.conn.execute("PRAGMA journal_mode=WAL;")  # Improve concurrency
            self.conn.execute("PRAGMA busy_timeout = 5000;") # Wait 5s if locked

            # Create tweets table
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
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create comments table (保留表结构，但不在此阶段填充数据)
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
            # Create indices for tweets table
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_author_id ON tweets(author_id)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_created_at ON tweets(created_at)')
            # Create indices for comments table
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_comment_tweet_id ON comments(tweet_id)')

            self.conn.commit()
            self.logger.info(f"Tweet database {self.tweets_db_path} initialized/connected successfully.")

        except sqlite3.Error as e:
            self.logger.error(f"Failed to initialize tweet database {self.tweets_db_path}: {e}")
            # If initialization fails, set conn/cursor to None to prevent further errors
            if self.conn:
                self.conn.close()
            self.conn = None
            self.cursor = None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during tweet DB initialization: {e}")
            if self.conn:
                self.conn.close()
            self.conn = None
            self.cursor = None

    def load_authors(self) -> List[Dict]:
        """从 followingA.db 加载作者信息"""
        authors = []
        conn_following = None
        try:
            # 检查文件是否存在
            if not os.path.exists(self.following_db_path):
                self.logger.error(f"Source database file not found: {self.following_db_path}. Cannot load authors.")
                return []

            # 使用正确的 followingA.db 路径连接
            conn_following = sqlite3.connect(self.following_db_path, timeout=10)
            conn_following.execute("PRAGMA query_only = ON;") # Read-only access
            cursor = conn_following.cursor()

            # 检查 users 表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone() is None:
                self.logger.error(f"Table 'users' not found in database: {self.following_db_path}. Cannot load authors.")
                return []

            cursor.execute("SELECT username, user_id FROM users WHERE user_id IS NOT NULL AND user_id != ''")
            rows = cursor.fetchall()
            # Filter out potential duplicates based on user_id if necessary, though DB should handle it
            seen_ids = set()
            for row in rows:
                user_id = row[1]
                if user_id not in seen_ids:
                    authors.append({"username": row[0], "author_id": user_id})
                    seen_ids.add(user_id)

            if authors:
                 sample_authors = [a.get('username', 'N/A') for a in authors[:5]]
                 self.logger.info(f"Loaded {len(authors)} unique authors from database {self.following_db_path}. Sample: {sample_authors}...")
            else:
                 self.logger.warning(f"No valid authors found in database: {self.following_db_path}")
            return authors

        except sqlite3.Error as e:
            self.logger.error(f"Database error loading authors from {self.following_db_path}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error loading authors from {self.following_db_path}: {e}")
            return []
        finally:
            # 确保关闭 followingA.db 的连接
            if conn_following:
                conn_following.close()

    @retry_on_error(max_retries=3, backoff_factor=1.0)
    async def get_user_tweets(self, author_id: str, max_tweets: int, session: aiohttp.ClientSession) -> List[Dict]:
        """Get tweets for a user using the user-tweets endpoint"""
        all_tweets = []
        if not author_id:
             self.logger.warning("No author_id provided, cannot fetch tweets.")
             return all_tweets
        try:
            url = f"{self.base_url}/user-tweets"
            cursor = ""
            pages_fetched = 0
            max_pages = (max_tweets // 50) + 2 # Estimate pages needed (API likely returns batches up to 50-100?)

            while len(all_tweets) < max_tweets and pages_fetched < max_pages:
                pages_fetched += 1
                data = {
                    "user_id": author_id,
                    "cursor": cursor
                }
                try:
                    # Use the provided session
                    async with session.post(url, headers=self.headers, json=data, timeout=120) as response:  # 增加超时时间到120秒
                        if response.status == 200:
                            try:
                                response_data = await response.json()
                            except json.JSONDecodeError:
                                 response_text = await response.text()
                                 self.logger.error(f"API returned invalid JSON fetching tweets for user {author_id}, page {pages_fetched}. Response: {response_text[:200]}...")
                                 break

                            tweets = response_data.get('tweets', [])
                            if not tweets:
                                self.logger.debug(f"No more tweets found for user {author_id}, page {pages_fetched}")
                                break

                            all_tweets.extend(tweets)
                            self.logger.debug(f"Fetched {len(tweets)} tweets for user {author_id} page {pages_fetched} (total now: {len(all_tweets)}/{max_tweets})")

                            if len(all_tweets) >= max_tweets:
                                all_tweets = all_tweets[:max_tweets]
                                self.logger.info(f"Reached max_tweets ({max_tweets}) for user {author_id}.")
                                break

                            cursor = response_data.get('next_cursor')
                            if not cursor:
                                self.logger.debug(f"No next cursor provided for user {author_id}. Ending tweet fetch.")
                                break
                            await asyncio.sleep(2) # Rate limiting between pages

                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 60))
                            self.logger.warning(f"Rate limited (429) fetching tweets page {pages_fetched} for user {author_id}. Waiting {retry_after} seconds...")
                            await asyncio.sleep(retry_after)
                            pages_fetched -= 1 # Decrement page count as we retry the same page
                            continue # Retry the same page

                        elif response.status == 404:
                             self.logger.warning(f"User {author_id} not found (404) by API.")
                             break
                        else:
                            error_text = await response.text()
                            self.logger.error(f"API error fetching tweets page {pages_fetched} for user {author_id}: Status {response.status}, {error_text[:200]}...")
                            break # Stop fetching tweets for this user on error

                except asyncio.TimeoutError:
                     raise  # 让装饰器处理重试
                except aiohttp.ClientError as client_err:
                     raise  # 让装饰器处理重试

            self.logger.info(f"Retrieved {len(all_tweets)} tweets in total for user ID {author_id}")
            return all_tweets

        except Exception as e:
            self.logger.error(f"Unexpected error getting tweets for user ID {author_id}: {e}")
            self.logger.error(traceback.format_exc())
            return []

    def save_tweet(self, author: Dict, tweet_data: Dict):
        """Save a tweet to the tweets.db"""
        if not self.conn or not self.cursor:
             self.logger.error("Database connection not available, cannot save tweet.")
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
                    self.logger.warning(f"Unable to parse tweet date: {created_at_str}")

            self.cursor.execute('''
                INSERT OR REPLACE INTO tweets
                (tweet_id, conversation_id, author_id, author_name, full_text, created_at,
                 likes_count, retweets_count, replies_count, views_count, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                tweet_data.get('id_str'),
                tweet_data.get('conversation_id_str'),
                author['author_id'],
                author['username'],
                tweet_data.get('full_text', ''),
                created_at_dt, # Store datetime object
                tweet_data.get('favorite_count', 0),
                tweet_data.get('retweet_count', 0),
                tweet_data.get('reply_count', 0),
                tweet_data.get('view_count', 0)
            ))
            # Commit handled in process_author or run loop
        except sqlite3.Error as e:
            self.logger.error(f"Database error saving tweet {tweet_data.get('id_str')} for author {author['username']}: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error saving tweet: {e}")

    async def process_author(self, author: Dict, max_tweets: int, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession):
        """Process tweets for a single author (不再处理评论)"""
        author_id = author.get('author_id')
        author_name = author.get('username', 'N/A')
        if not author_id:
            self.logger.warning(f"Skipping author due to missing author_id: {author}")
            return

        async with semaphore:
            self.logger.info(f"Starting tweet processing for author: {author_name} ({author_id})")
            processed_tweets = 0
            try:
                # Get tweets for the author using the shared session
                tweets = await self.get_user_tweets(author_id, max_tweets, session)
                self.logger.info(f"Processing {len(tweets)} tweets found for author {author_name}")

                for tweet in tweets:
                    # Save the tweet
                    self.save_tweet(author, tweet)
                    processed_tweets += 1

                    # 移除了评论处理逻辑

                    # Optional short sleep between processing tweets of the same author
                    await asyncio.sleep(0.2) # Shorter sleep

                # Commit transactions for this author after processing all their tweets
                if self.conn:
                    self.conn.commit()

            except Exception as e:
                self.logger.error(f"Error processing author {author_name} ({author_id}): {e}")
                self.logger.error(traceback.format_exc())
                # Rollback any potential partial changes for this author on error
                if self.conn:
                    self.conn.rollback()
            finally:
                self.logger.info(f"Finished tweet processing for {author_name} ({author_id}). Saved {processed_tweets} tweets.")


    async def run(self, max_tweets: int, max_concurrent_tasks: int = 5):
        """Run the tweet collection crawler (不再收集评论)"""
        if not self.conn:
             self.logger.error("Tweet database connection is not available. Aborting tweet collection.")
             return
        run_start_time = time.time()
        self.logger.info(f"--- Starting Tweet Collection Run (Max Tweets: {max_tweets}, Concurrency: {max_concurrent_tasks}) ---")
        try:
            authors = self.load_authors()
            if not authors:
                 self.logger.warning("No authors loaded, skipping tweet collection.")
                 return

            semaphore = asyncio.Semaphore(max_concurrent_tasks)
            self.logger.info(f"Processing {len(authors)} authors...")

            # Create a single aiohttp session to be reused by all tasks
            async with aiohttp.ClientSession() as session:
                tasks = []
                for author in authors:
                    # Schedule the processing task for each author, passing the session
                    task = asyncio.create_task(self.process_author(author, max_tweets, semaphore, session))
                    tasks.append(task)

                # Wait for all scheduled tasks to complete
                if tasks:
                    # Optional: Add progress reporting using asyncio.as_completed if needed
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    # Log any exceptions that occurred in tasks
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            self.logger.error(f"Error in task for author {authors[i].get('username', 'N/A')}: {result}")
                    self.logger.info("All author tweet processing tasks have completed (or failed).")
                else:
                    self.logger.info("No author tasks were scheduled.")

        except Exception as e:
             self.logger.error(f"Error occurred during the main tweet crawler run: {e}")
             self.logger.error(traceback.format_exc())
        finally:
            # Ensure the main connection (to tweets.db) is closed
            if hasattr(self, 'conn') and self.conn:
                try:
                    self.conn.close()
                    self.logger.info(f"Tweet database {self.tweets_db_path} connection closed.")
                except Exception as close_err:
                     self.logger.error(f"Error closing tweet DB connection: {close_err}")
            run_end_time = time.time()
            self.logger.info(f"--- Tweet Collection Run Finished (Duration: {run_end_time - run_start_time:.2f} seconds) ---")

# This part is primarily for standalone testing/execution of 1.py
async def main_for_script():
    parser = argparse.ArgumentParser(description="TweetCrawler (Standalone Execution)")
    parser.add_argument("--max_tweets", type=int, default=20, help="Max tweets per user")
    parser.add_argument("--db_dir", type=str, required=True, help="Directory containing followingA.db and for creating tweets.db")
    parser.add_argument("--api_key", type=str, default="你的api", help="TweetScout API Key")
    parser.add_argument("--max_concurrent_tasks", type=int, default=1,
                    help="并发作者任务数")
    args = parser.parse_args()

    print(f"Running TweetCrawler standalone with db_dir: {args.db_dir}")
    # Load API key securely if possible, e.g., from environment variable
    api_key = os.getenv("TWEETSCOUT_API_KEY", args.api_key)
    if api_key == "你的api": 
        print("Warning: Using default API Key for standalone run.")

    crawler = TweetCrawler(
        api_key=api_key,
        db_dir=args.db_dir
    )
    await crawler.run(args.max_tweets, max_concurrent_tasks=args.max_concurrent_tasks)


if __name__ == "__main__":
    asyncio.run(main_for_script())