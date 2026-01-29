#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twitter 爬虫模块 - 简化版
整合用户信息获取和推文抓取功能

使用方法:
    from twitter_crawler import TwitterCrawler
    
    crawler = TwitterCrawler(api_key="your-tweetscout-key")
    crawler.crawl_user("username", max_tweets=100, skip_comments=True)
"""

import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except ImportError:
    from requests.packages.urllib3.util.retry import Retry
import aiohttp
import asyncio
import json
import logging
import sqlite3
import time
import os
import traceback
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional, Any
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TwitterCrawler:
    """Twitter 爬虫类 - 整合用户信息获取和推文抓取"""
    
    def __init__(self, api_key: str, output_dir: str = ".", db_name: str = "twitter_data.db"):
        """
        初始化爬虫
        
        Args:
            api_key: TweetScout API 密钥
            output_dir: 输出目录（默认当前目录）
            db_name: 数据库文件名（默认 twitter_data.db）
        """
        self.api_key = api_key
        self.base_url = "https://api.tweetscout.io/v2"
        self.output_dir = output_dir
        self.db_path = os.path.join(output_dir, db_name)
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置请求头
        self.headers = {
            "ApiKey": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # 创建同步请求会话（用于获取用户信息）
        self.session = self._create_session()
        
        # 设置日志
        self._setup_logging()
        
        # 初始化数据库
        self.conn = None
        self.cursor = None
        self._init_database()
    
    def _create_session(self) -> requests.Session:
        """创建具有重试策略的requests会话"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=True
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_maxsize=10,
            pool_block=True
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.verify = False
        
        return session
    
    def _setup_logging(self):
        """设置日志配置"""
        log_file = os.path.join(self.output_dir, "twitter_crawler.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("TwitterCrawler")
    
    def _init_database(self):
        """初始化SQLite数据库"""
        try:
            # 备份旧数据库（如果存在）
            if os.path.exists(self.db_path):
                backup_path = f"{self.db_path}.{int(time.time())}.bak"
                os.rename(self.db_path, backup_path)
                self.logger.info(f"已备份现有数据库到 {backup_path}")
            
            # 连接数据库
            self.conn = sqlite3.connect(
                self.db_path, 
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES,
                timeout=10
            )
            self.cursor = self.conn.cursor()
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA busy_timeout = 5000;")
            
            # 创建用户信息表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    followers_count INTEGER,
                    friends_count INTEGER,
                    tweets_count INTEGER,
                    avatar_url TEXT,
                    banner_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建推文表
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
            
            # 创建评论表
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
            
            # 创建索引
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_username ON users(username)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_author_id ON tweets(author_id)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweet_created_at ON tweets(created_at)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_comment_tweet_id ON comments(tweet_id)')
            
            self.conn.commit()
            self.logger.info(f"数据库 {self.db_path} 初始化成功")
            
        except sqlite3.Error as e:
            self.logger.error(f"初始化数据库失败: {e}")
            if self.conn:
                self.conn.close()
            self.conn = None
            self.cursor = None
        except Exception as e:
            self.logger.error(f"初始化数据库时发生意外错误: {e}")
            if self.conn:
                self.conn.close()
            self.conn = None
            self.cursor = None
    
    def get_user_info(self, username: str) -> Dict[str, Any]:
        """
        获取用户信息
        
        Args:
            username: Twitter 用户名（不含 @）
            
        Returns:
            用户信息字典，包含 id, screen_name, followers_count 等
        """
        try:
            url = f"{self.base_url}/info/{username}"
            
            response = self.session.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"获取到 {username} 的用户信息")
                return data
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                self.logger.warning(f"达到速率限制。等待 {retry_after} 秒...")
                time.sleep(retry_after)
                return self.get_user_info(username)  # 等待后重试
            elif response.status_code == 404:
                self.logger.warning(f"用户 {username} 未找到")
            else:
                self.logger.error(f"获取 {username} 的用户信息失败: 状态 {response.status_code}, {response.text}")
                
        except Exception as e:
            self.logger.error(f"获取 {username} 的用户信息时出错: {str(e)}")
            
        return {}
    
    def save_user_info(self, user_info: Dict[str, Any]) -> bool:
        """
        保存用户信息到数据库
        
        Args:
            user_info: 用户信息字典
            
        Returns:
            是否保存成功
        """
        if not user_info or 'id' not in user_info:
            return False
        
        if not self.conn or not self.cursor:
            self.logger.error("数据库连接不可用，无法保存用户信息")
            return False
        
        try:
            # 获取头像URL并转换为大尺寸
            avatar_url = user_info.get('avatar', '')
            if avatar_url and '_normal.' in avatar_url:
                avatar_url = avatar_url.replace('_normal.', '_400x400.')
            
            # 获取背景图片URL
            banner_url = user_info.get('banner', '')
            
            # 保存到数据库
            self.cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, followers_count, friends_count, tweets_count, avatar_url, banner_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_info.get('id'),
                user_info.get('screen_name'),
                user_info.get('followers_count', 0),
                user_info.get('friends_count', 0),
                user_info.get('tweets_count', 0),
                avatar_url,
                banner_url
            ))
            
            self.conn.commit()
            self.logger.info(f"保存了 {user_info.get('screen_name')} 的用户信息 (ID: {user_info.get('id')})")
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"保存用户信息时数据库错误: {str(e)}")
            self.conn.rollback()
            return False
        except Exception as e:
            self.logger.error(f"保存用户信息时出错: {str(e)}")
            self.conn.rollback()
            return False
    
    async def get_user_tweets(self, user_id: str, max_tweets: int, session: aiohttp.ClientSession) -> List[Dict]:
        """
        获取用户的推文（异步）
        
        Args:
            user_id: 用户ID
            max_tweets: 最大推文数
            session: aiohttp 会话
            
        Returns:
            推文列表
        """
        all_tweets = []
        if not user_id:
            self.logger.warning("未提供user_id，无法获取推文")
            return all_tweets
        
        try:
            url = f"{self.base_url}/user-tweets"
            cursor = ""
            pages_fetched = 0
            max_pages = (max_tweets // 20) + 2
            
            while len(all_tweets) < max_tweets and pages_fetched < max_pages:
                pages_fetched += 1
                data = {
                    "user_id": user_id,
                    "cursor": cursor
                }
                
                try:
                    async with session.post(url, headers=self.headers, json=data, timeout=60) as response:
                        if response.status == 200:
                            try:
                                response_data = await response.json()
                            except json.JSONDecodeError:
                                response_text = await response.text()
                                self.logger.error(f"获取用户 {user_id} 的推文时API返回无效JSON, 页 {pages_fetched}")
                                break
                            
                            tweets = response_data.get('tweets', [])
                            if not tweets:
                                self.logger.debug(f"用户 {user_id} 没有更多推文, 页 {pages_fetched}")
                                break
                            
                            all_tweets.extend(tweets)
                            self.logger.debug(f"为用户 {user_id} 获取到 {len(tweets)} 条推文，页 {pages_fetched} (总计: {len(all_tweets)}/{max_tweets})")
                            
                            if len(all_tweets) >= max_tweets:
                                all_tweets = all_tweets[:max_tweets]
                                break
                            
                            cursor = response_data.get('next_cursor')
                            if not cursor:
                                break
                            
                            await asyncio.sleep(2)  # 页面之间的速率限制
                            
                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 60))
                            self.logger.warning(f"速率限制 (429)，等待 {retry_after} 秒...")
                            await asyncio.sleep(retry_after)
                            pages_fetched -= 1
                            continue
                            
                        elif response.status == 404:
                            self.logger.warning(f"API未找到用户 {user_id} (404)")
                            break
                        else:
                            error_text = await response.text()
                            self.logger.error(f"获取推文页 {pages_fetched}，用户 {user_id} 时API错误: 状态 {response.status}")
                            break
                            
                except asyncio.TimeoutError:
                    self.logger.error(f"获取推文页 {pages_fetched}，用户 {user_id} 超时")
                    break
                except aiohttp.ClientError as client_err:
                    self.logger.error(f"获取推文页 {pages_fetched}，用户 {user_id} 网络错误: {client_err}")
                    break
            
            self.logger.info(f"总共为用户ID {user_id} 获取到 {len(all_tweets)} 条推文")
            return all_tweets
            
        except Exception as e:
            self.logger.error(f"获取用户ID {user_id} 的推文时意外错误: {e}")
            self.logger.error(traceback.format_exc())
            return []
    
    async def get_tweet_comments(self, tweet_id: str, conversation_id: str, session: aiohttp.ClientSession) -> List[Dict]:
        """
        获取推文的评论（异步）
        
        Args:
            tweet_id: 推文ID
            conversation_id: 对话ID
            session: aiohttp 会话
            
        Returns:
            评论列表
        """
        all_comments = []
        if not conversation_id:
            return all_comments
        
        try:
            url = f"{self.base_url}/search-tweets"
            query = f"conversation_id:{conversation_id}"
            next_cursor = ""
            max_comment_pages = 5  # 限制页数
            
            for page in range(max_comment_pages):
                data = {
                    "query": query,
                    "next_cursor": next_cursor
                }
                
                try:
                    async with session.post(url, headers=self.headers, json=data, timeout=60) as response:
                        if response.status == 200:
                            response_text = await response.text()
                            if not response_text.strip():
                                break
                            
                            try:
                                response_data = json.loads(response_text)
                            except json.JSONDecodeError:
                                break
                            
                            comments = response_data.get("tweets", [])
                            if not comments:
                                break
                            
                            # 过滤原始推文
                            filtered_comments = [
                                c for c in comments
                                if c.get("id_str") != tweet_id and c.get("conversation_id_str") == conversation_id
                            ]
                            all_comments.extend(filtered_comments)
                            
                            next_cursor = response_data.get("next_cursor")
                            if not next_cursor:
                                break
                            
                            await asyncio.sleep(2)
                            
                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 60))
                            self.logger.warning(f"速率限制 (429) 获取评论，等待 {retry_after} 秒...")
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            break
                            
                except (asyncio.TimeoutError, aiohttp.ClientError):
                    break
            
            return all_comments
            
        except Exception as e:
            self.logger.error(f"搜索推文 {tweet_id} 的评论时意外错误: {e}")
            return []
    
    def save_tweet(self, user_info: Dict, tweet_data: Dict):
        """保存推文到数据库"""
        if not self.conn or not self.cursor:
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
            
            # 序列化复杂对象
            entities_json = json.dumps(tweet_data.get('entities'), ensure_ascii=False) if tweet_data.get('entities') else None
            quoted_status_json = json.dumps(tweet_data.get('quoted_status'), ensure_ascii=False) if tweet_data.get('quoted_status') else None
            retweeted_status_json = json.dumps(tweet_data.get('retweeted_status'), ensure_ascii=False) if tweet_data.get('retweeted_status') else None
            user_json = json.dumps(tweet_data.get('user'), ensure_ascii=False) if tweet_data.get('user') else None
            
            # 尝试多种可能的字段名来获取浏览量数据
            view_count = 0
            public_metrics = tweet_data.get('public_metrics', {})
            if isinstance(public_metrics, dict):
                # 尝试从 public_metrics 中获取
                view_count = public_metrics.get('view_count', 0) or public_metrics.get('impression_count', 0)
            
            # 如果 public_metrics 中没有，尝试直接字段
            if view_count == 0:
                view_count = (tweet_data.get('view_count') or 
                             tweet_data.get('views_count') or 
                             tweet_data.get('views') or 
                             tweet_data.get('impression_count') or 0)
            
            # 确保是整数
            try:
                view_count = int(view_count) if view_count else 0
            except (ValueError, TypeError):
                view_count = 0
            
            # 如果仍然没有获取到浏览量数据，记录警告（仅对前几条推文记录，避免日志过多）
            if view_count == 0 and len([k for k in tweet_data.keys() if 'view' in k.lower() or 'impression' in k.lower()]) == 0:
                # 只在第一次遇到这种情况时记录详细日志
                if not hasattr(self, '_view_count_warning_logged'):
                    self.logger.warning(f"未找到浏览量数据字段。推文数据中的可用字段: {list(tweet_data.keys())[:10]}")
                    if public_metrics:
                        self.logger.warning(f"public_metrics 中的字段: {list(public_metrics.keys())}")
                    self._view_count_warning_logged = True
            
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
                user_info.get('id'),
                user_info.get('screen_name'),
                tweet_data.get('full_text', ''),
                created_at_dt,
                tweet_data.get('favorite_count', 0),
                tweet_data.get('retweet_count', 0),
                tweet_data.get('reply_count', 0),
                view_count,
                tweet_data.get('bookmark_count', 0),
                tweet_data.get('in_reply_to_status_id_str'),
                1 if tweet_data.get('is_quote_status', False) else 0,
                tweet_data.get('quote_count', 0),
                entities_json,
                quoted_status_json,
                retweeted_status_json,
                user_json
            ))
            
        except sqlite3.Error as e:
            self.logger.error(f"保存推文时数据库错误: {e}")
        except Exception as e:
            self.logger.error(f"保存推文时意外错误: {e}")
    
    def save_comment(self, tweet_id: str, comment_data: Dict):
        """保存评论到数据库"""
        if not self.conn or not self.cursor:
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
                    pass
            
            self.cursor.execute('''
                INSERT OR IGNORE INTO comments
                (tweet_id, comment_id, author_id, comment_text, created_at, likes_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                tweet_id,
                comment_data.get('id_str'),
                comment_data.get('user', {}).get('id_str'),
                comment_data.get('full_text', ''),
                created_at_dt,
                comment_data.get('favorite_count', 0)
            ))
            
        except sqlite3.Error as e:
            self.logger.error(f"保存评论时数据库错误: {e}")
        except Exception as e:
            self.logger.error(f"保存评论时意外错误: {e}")
    
    async def _crawl_tweets_async(self, user_info: Dict, max_tweets: int, skip_comments: bool = False):
        """异步抓取推文和评论"""
        user_id = user_info.get('id')
        username = user_info.get('screen_name', 'N/A')
        
        if not user_id:
            self.logger.warning(f"用户 {username} 缺少 user_id，跳过推文抓取")
            return
        
        self.logger.info(f"开始抓取用户 {username} ({user_id}) 的推文")
        
        try:
            async with aiohttp.ClientSession() as session:
                # 获取推文
                tweets = await self.get_user_tweets(user_id, max_tweets, session)
                self.logger.info(f"为用户 {username} 找到 {len(tweets)} 条推文")
                
                for tweet in tweets:
                    # 保存推文
                    self.save_tweet(user_info, tweet)
                    
                    # 如果需要抓取评论
                    if not skip_comments:
                        conversation_id = tweet.get("conversation_id_str")
                        tweet_id = tweet.get("id_str")
                        
                        if conversation_id and tweet_id and tweet.get('reply_count', 0) > 0:
                            comments = await self.get_tweet_comments(tweet_id, conversation_id, session)
                            if comments:
                                for comment in comments:
                                    self.save_comment(tweet_id, comment)
                                self.logger.debug(f"保存推文 {tweet_id} 的 {len(comments)} 条评论")
                    
                    await asyncio.sleep(0.2)
                
                # 提交事务
                if self.conn:
                    self.conn.commit()
                    
        except Exception as e:
            self.logger.error(f"抓取用户 {username} 的推文时出错: {e}")
            self.logger.error(traceback.format_exc())
            if self.conn:
                self.conn.rollback()
    
    def crawl_user(self, username: str, max_tweets: int = 100, skip_comments: bool = True) -> Dict[str, Any]:
        """
        爬取指定用户的信息和推文（主入口方法）
        
        Args:
            username: Twitter 用户名（不含 @）
            max_tweets: 最大推文数（默认 100）
            skip_comments: 是否跳过评论抓取（默认 True，跳过评论可以加快速度）
            
        Returns:
            包含用户信息和统计的字典
        """
        if not self.conn:
            self.logger.error("数据库连接不可用，无法执行爬取")
            return {}
        
        self.logger.info(f"开始爬取用户: {username}")
        start_time = time.time()
        
        # 1. 获取用户信息
        self.logger.info(f"步骤 1/2: 获取用户信息...")
        user_info = self.get_user_info(username)
        
        if not user_info or 'id' not in user_info:
            self.logger.error(f"无法获取用户 {username} 的信息")
            return {}
        
        # 保存用户信息
        self.save_user_info(user_info)
        
        # 2. 抓取推文
        self.logger.info(f"步骤 2/2: 抓取推文...")
        asyncio.run(self._crawl_tweets_async(user_info, max_tweets, skip_comments))
        
        # 统计结果
        if self.conn:
            self.cursor.execute('SELECT COUNT(*) FROM tweets WHERE author_id = ?', (user_info.get('id'),))
            tweet_count = self.cursor.fetchone()[0]
            
            if not skip_comments:
                self.cursor.execute('''
                    SELECT COUNT(*) FROM comments 
                    WHERE tweet_id IN (SELECT tweet_id FROM tweets WHERE author_id = ?)
                ''', (user_info.get('id'),))
                comment_count = self.cursor.fetchone()[0]
            else:
                comment_count = 0
        else:
            tweet_count = 0
            comment_count = 0
        
        elapsed_time = time.time() - start_time
        
        result = {
            'username': username,
            'user_id': user_info.get('id'),
            'followers_count': user_info.get('followers_count', 0),
            'tweets_crawled': tweet_count,
            'comments_crawled': comment_count,
            'elapsed_time': elapsed_time,
            'db_path': self.db_path
        }
        
        self.logger.info(f"爬取完成: {username}")
        self.logger.info(f"  推文数: {tweet_count}, 评论数: {comment_count}, 耗时: {elapsed_time:.2f}秒")
        
        return result
    
    def get_user_data(self, username: str) -> Optional[Dict[str, Any]]:
        """
        从数据库获取用户信息
        
        Args:
            username: Twitter 用户名
            
        Returns:
            用户信息字典，如果不存在则返回 None
        """
        if not self.conn:
            return None
        
        try:
            self.cursor.execute('''
                SELECT user_id, username, followers_count, friends_count, 
                       tweets_count, avatar_url, banner_url
                FROM users WHERE username = ?
            ''', (username,))
            
            row = self.cursor.fetchone()
            if row:
                return {
                    'user_id': row[0],
                    'username': row[1],
                    'followers_count': row[2],
                    'friends_count': row[3],
                    'tweets_count': row[4],
                    'avatar_url': row[5],
                    'banner_url': row[6]
                }
        except Exception as e:
            self.logger.error(f"获取用户数据时出错: {e}")
        
        return None
    
    def get_tweets(self, username: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        从数据库获取用户的推文
        
        Args:
            username: Twitter 用户名
            limit: 限制返回的推文数量（None 表示全部）
            
        Returns:
            推文列表
        """
        if not self.conn:
            return []
        
        try:
            query = '''
                SELECT tweet_id, full_text, created_at, likes_count, 
                       retweets_count, replies_count, views_count
                FROM tweets WHERE author_name = ?
                ORDER BY created_at DESC
            '''
            
            if limit:
                query += f' LIMIT {limit}'
            
            self.cursor.execute(query, (username,))
            rows = self.cursor.fetchall()
            
            tweets = []
            for row in rows:
                tweets.append({
                    'tweet_id': row[0],
                    'full_text': row[1],
                    'created_at': row[2],
                    'likes_count': row[3],
                    'retweets_count': row[4],
                    'replies_count': row[5],
                    'views_count': row[6]
                })
            
            return tweets
            
        except Exception as e:
            self.logger.error(f"获取推文时出错: {e}")
            return []
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                self.conn.close()
                self.logger.info("数据库连接已关闭")
            except Exception as e:
                self.logger.error(f"关闭数据库连接时出错: {e}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Twitter 爬虫 - 简化版")
    parser.add_argument("username", help="Twitter 用户名（不含 @）")
    parser.add_argument("--api-key", default=None, help="TweetScout API 密钥（也可通过环境变量 TWEETSCOUT_API_KEY 设置）")
    parser.add_argument("--max-tweets", type=int, default=100, help="最大推文数（默认 100）")
    parser.add_argument("--skip-comments", action="store_true", default=True, help="跳过评论抓取（默认 True）")
    parser.add_argument("--output-dir", default=".", help="输出目录（默认当前目录）")
    parser.add_argument("--db-name", default="twitter_data.db", help="数据库文件名（默认 twitter_data.db）")
    
    args = parser.parse_args()
    
    # 获取 API 密钥
    api_key = args.api_key or os.getenv("TWEETSCOUT_API_KEY")
    if not api_key:
        print("❌ 错误: 请提供 TweetScout API 密钥")
        print("   方法1: 通过命令行参数 --api-key")
        print("   方法2: 设置环境变量 TWEETSCOUT_API_KEY")
        return 1
    
    # 创建爬虫并执行
    crawler = TwitterCrawler(
        api_key=api_key,
        output_dir=args.output_dir,
        db_name=args.db_name
    )
    
    try:
        result = crawler.crawl_user(
            username=args.username,
            max_tweets=args.max_tweets,
            skip_comments=args.skip_comments
        )
        
        if result:
            print("\n✅ 爬取完成！")
            print(f"   用户名: {result['username']}")
            print(f"   用户ID: {result['user_id']}")
            print(f"   粉丝数: {result['followers_count']:,}")
            print(f"   推文数: {result['tweets_crawled']}")
            print(f"   评论数: {result['comments_crawled']}")
            print(f"   耗时: {result['elapsed_time']:.2f} 秒")
            print(f"   数据库: {result['db_path']}")
            return 0
        else:
            print("❌ 爬取失败")
            return 1
            
    finally:
        crawler.close()


if __name__ == "__main__":
    exit(main())

