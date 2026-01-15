import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import json
import logging
import sqlite3
import time
from datetime import datetime
import urllib3
import os
import argparse
from typing import List, Dict, Any, Optional

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TwitterUserCrawler:
    def __init__(self, api_key: str, usernames_file: str = None, usernames: List[str] = None, 
                 output_json: str = None, db_path: str = None, log_path: str = None):
        self.api_key = api_key
        self.base_url = "https://api.tweetscout.io/v2"
        self.usernames_file = usernames_file
        self.usernames_list = usernames or []
        
        # 设置输出路径
        self.output_json = output_json or "twitter_users.json"
        
        # 设置数据库路径 - 默认在temp目录
        if db_path:
            self.db_path = db_path
        else:
            # 如果在scripts目录下运行，数据库放在temp目录
            temp_dir = "../data/temp"
            os.makedirs(temp_dir, exist_ok=True)
            self.db_path = os.path.join(temp_dir, "twitter_users.db")
        
        # 设置日志路径
        if log_path:
            self.log_path = log_path
        else:
            # 默认日志路径
            logs_dir = "../logs"
            os.makedirs(logs_dir, exist_ok=True)
            self.log_path = os.path.join(logs_dir, "user_crawler.log")
        
        self.headers = {
            "ApiKey": api_key,
            "Accept": "application/json"
        }
        self.session = self._create_session()
        self._setup_logging()
        self._init_database()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy"""
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
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_path),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("TwitterUserCrawler")

    def _init_database(self):
        """Initialize the SQLite database"""
        if not os.path.exists(self.db_path):
            self.logger.info(f"Creating new database at {self.db_path}")
        
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Create users table
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS twitter_users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                name TEXT,
                description TEXT,
                followers_count INTEGER,
                friends_count INTEGER,
                tweets_count INTEGER,
                register_date TEXT,
                avatar TEXT,
                banner TEXT,
                verified BOOLEAN,
                can_dm BOOLEAN,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_username ON twitter_users(username);
            CREATE INDEX IF NOT EXISTS idx_user_id ON twitter_users(user_id);
        ''')
        self.conn.commit()

    def load_usernames(self) -> List[str]:
        """Load usernames from file if provided"""
        if not self.usernames_file:
            return self.usernames_list
            
        if not os.path.exists(self.usernames_file):
            self.logger.error(f"Input file {self.usernames_file} does not exist")
            return []
            
        try:
            with open(self.usernames_file, 'r', encoding='utf-8') as f:
                if self.usernames_file.endswith('.json'):
                    data = json.load(f)
                    if isinstance(data, list):
                        # Specifically handle authors.json format
                        if data and isinstance(data[0], dict):
                            if 'username' in data[0]:
                                usernames = [user['username'] for user in data]
                            elif 'author_username' in data[0]:
                                usernames = [user['author_username'] for user in data]
                            else:
                                # Try to find username field by inspecting keys
                                username_fields = ['username', 'author_username', 'screen_name', 'handle']
                                for field in username_fields:
                                    if field in data[0]:
                                        usernames = [user[field] for user in data if field in user]
                                        break
                                else:
                                    # If no known username field is found, log the keys
                                    self.logger.warning(f"Could not identify username field. Available fields: {list(data[0].keys())}")
                                    usernames = []
                        else:
                            usernames = [u for u in data if isinstance(u, str)]
                    else:
                        usernames = []
                else:
                    usernames = [line.strip() for line in f if line.strip()]
                
                self.logger.info(f"Loaded {len(usernames)} usernames from {self.usernames_file}")
                return usernames
        except Exception as e:
            self.logger.error(f"Error loading usernames file: {str(e)}")
            return self.usernames_list

    def get_user_id(self, username: str) -> Optional[str]:
        """Get user ID from Twitter handle"""
        try:
            url = f"{self.base_url}/handle-to-id/{username}"
            
            response = self.session.get(
                url, 
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'id' in data:
                    self.logger.info(f"Retrieved user ID for {username}: {data['id']}")
                    return data['id']
                else:
                    self.logger.warning(f"No ID found in response for {username}")
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                self.logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self.get_user_id(username)  # Retry after waiting
            else:
                self.logger.error(f"Failed to get user ID for {username}: Status {response.status_code}, {response.text}")
                
        except Exception as e:
            self.logger.error(f"Error getting user ID for {username}: {str(e)}")
            
        return None

    def get_user_info(self, username: str) -> Dict[str, Any]:
        """Get detailed user information by username"""
        try:
            url = f"{self.base_url}/info/{username}"
            
            response = self.session.get(
                url, 
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"Retrieved user info for {username}")
                return data
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                self.logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self.get_user_info(username)  # Retry after waiting
            elif response.status_code == 404:
                self.logger.warning(f"User {username} not found")
            else:
                self.logger.error(f"Failed to get user info for {username}: Status {response.status_code}, {response.text}")
                
        except Exception as e:
            self.logger.error(f"Error getting user info for {username}: {str(e)}")
            
        return {}

    def get_user_info_by_id(self, user_id: str) -> Dict[str, Any]:
        """Get detailed user information by user ID"""
        try:
            url = f"{self.base_url}/info-id/{user_id}"
            
            response = self.session.get(
                url, 
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"Retrieved user info for ID {user_id}")
                return data
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                self.logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self.get_user_info_by_id(user_id)  # Retry after waiting
            elif response.status_code == 404:
                self.logger.warning(f"User ID {user_id} not found")
            else:
                self.logger.error(f"Failed to get user info for ID {user_id}: Status {response.status_code}, {response.text}")
                
        except Exception as e:
            self.logger.error(f"Error getting user info for ID {user_id}: {str(e)}")
            
        return {}

    def save_user(self, user_info: Dict[str, Any]) -> None:
        """Save user information to database"""
        if not user_info or 'id' not in user_info:
            return
        
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO twitter_users 
                (user_id, username, name, description, 
                followers_count, friends_count, tweets_count,
                register_date, avatar, banner, verified, can_dm,
                last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                user_info.get('id'),
                user_info.get('screen_name'),
                user_info.get('name'),
                user_info.get('description'),
                user_info.get('followers_count', 0),
                user_info.get('friends_count', 0),
                user_info.get('tweets_count', 0),
                user_info.get('register_date'),
                user_info.get('avatar'),
                user_info.get('banner'),
                user_info.get('verified', False),
                user_info.get('can_dm', False)
            ))
            
            self.conn.commit()
            self.logger.info(f"Saved user information for {user_info.get('screen_name')} (ID: {user_info.get('id')})")
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error saving user: {str(e)}")
            self.conn.rollback()
        except Exception as e:
            self.logger.error(f"Error saving user: {str(e)}")
            self.conn.rollback()

    def process_username(self, username: str) -> None:
        """Process a single username to get ID and information"""
        try:
            self.logger.info(f"Processing username: {username}")
            
            # Get user information directly from username
            user_info = self.get_user_info(username)
            
            if user_info and 'id' in user_info:
                self.save_user(user_info)
            else:
                # Try getting user ID first if the direct info request failed
                user_id = self.get_user_id(username)
                if user_id:
                    user_info = self.get_user_info_by_id(user_id)
                    if user_info:
                        self.save_user(user_info)
                    else:
                        self.logger.warning(f"Could not retrieve info for {username} (ID: {user_id})")
                else:
                    self.logger.warning(f"Could not retrieve ID for {username}")
            
            # Add a small delay between requests
            time.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Error processing username {username}: {str(e)}")

    def get_statistics(self) -> None:
        """Get and log statistics about collected data"""
        try:
            # Get total users
            self.cursor.execute("SELECT COUNT(*) FROM twitter_users")
            total_users = self.cursor.fetchone()[0]
            
            # Get user with highest follower count
            self.cursor.execute(
                "SELECT username, followers_count FROM twitter_users ORDER BY followers_count DESC LIMIT 1"
            )
            top_follower = self.cursor.fetchone()
            
            # Get verified vs non-verified users
            self.cursor.execute("SELECT COUNT(*) FROM twitter_users WHERE verified = 1")
            verified_users = self.cursor.fetchone()[0]
            
            self.logger.info(f"\nCrawling Statistics:")
            self.logger.info(f"Total users collected: {total_users}")
            if top_follower:
                self.logger.info(f"User with most followers: {top_follower[0]} ({top_follower[1]} followers)")
            self.logger.info(f"Verified users: {verified_users}")
            self.logger.info(f"Non-verified users: {total_users - verified_users}")
            
        except sqlite3.Error as e:
            self.logger.error(f"Error getting statistics: {str(e)}")

    def export_to_json(self, output_file: str = None) -> None:
        """Export collected data to JSON file"""
        if output_file is None:
            output_file = self.output_json
            
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            self.cursor.execute(
                "SELECT * FROM twitter_users"
            )
            
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            
            data = []
            for row in rows:
                user_data = dict(zip(columns, row))
                data.append(user_data)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Exported {len(data)} users to {output_file}")
            
        except Exception as e:
            self.logger.error(f"Error exporting data to JSON: {str(e)}")

    def close_connection(self):
        """Close database connection"""
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
                self.logger.info("Database connection closed")
            except Exception as e:
                self.logger.error(f"Error closing database connection: {str(e)}")

    def run(self, export_json: bool = True) -> None:
        """Run the crawler on all usernames"""
        try:
            usernames = self.load_usernames()
            if not usernames:
                self.logger.warning("No usernames provided. Exiting.")
                return

            self.logger.info(f"Starting to process {len(usernames)} usernames")

            for i, username in enumerate(usernames, 1):
                self.process_username(username)
                if i % 10 == 0:
                    self.logger.info(f"Processed {i}/{len(usernames)} usernames")

            self.get_statistics()

            # 如果 export_json 为 True (默认情况)，就在这里导出
            if export_json:
                self.export_to_json()

        except Exception as e:
            self.logger.error(f"Error in main run loop: {str(e)}")

        finally:
            # 根据 export_json 参数决定是否关闭连接
            if export_json:
                self.close_connection()
                self.logger.info("Crawler finished, database connection closed (within run, export_json=True)")
            else:
                self.logger.info("Crawler finished run (DB connection left open for explicit export/close by caller)")

def main():
    parser = argparse.ArgumentParser(description='Twitter User Crawler - 抓取种子用户信息')
    parser.add_argument('--input', '-i', 
                       help='输入文件路径 (author.json)')
    parser.add_argument('--output', '-o', 
                       help='输出JSON文件路径 (默认: data/input/twitter_users.json)')
    parser.add_argument('--export_json', action='store_true',
                       help='是否导出JSON文件')
    parser.add_argument('--api_key', 
                       default="你的api",
                       help='TweetScout API Key')
    parser.add_argument('--db_path',
                       help='数据库文件路径 (默认: ../data/temp/twitter_users.db)')
    parser.add_argument('--log_path',
                       help='日志文件路径 (默认: ../logs/user_crawler.log)')
    
    args = parser.parse_args()
    
    # 设置默认路径
    if not args.input:
        # 尝试从不同位置找到author.json
        possible_paths = [
            "author.json",
            "../data/input/author.json",
            "data/input/author.json"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                args.input = path
                break
        else:
            print("❌ 未找到输入文件 author.json，请使用 --input 指定路径")
            return
    
    if not args.output:
        # 默认输出到 data/input/twitter_users.json
        if os.path.exists("../data/input"):
            args.output = "../data/input/twitter_users.json"
        elif os.path.exists("data/input"):
            args.output = "data/input/twitter_users.json"
        else:
            args.output = "twitter_users.json"
    
    print(f"📁 输入文件: {args.input}")
    print(f"📁 输出文件: {args.output}")
    print(f"📊 导出JSON: {args.export_json}")
    
    # 创建爬虫实例
    crawler = TwitterUserCrawler(
        api_key=args.api_key,
        usernames_file=args.input,
        output_json=args.output,
        db_path=args.db_path,
        log_path=args.log_path
    )
    
    # 运行爬虫
    crawler.run(export_json=args.export_json)

if __name__ == "__main__":
    main()