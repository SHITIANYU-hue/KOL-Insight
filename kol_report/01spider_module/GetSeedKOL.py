#!/usr/bin/env python3
# GetSeedKOL.py - 从指定KOL列表获取详细信息并准备followingA.db
# 简化版，不再需要复杂的关注关系抓取

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

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class GetSeedKOL:
    def __init__(self, api_key: str, input_file: str):
        self.api_key = api_key
        self.base_url = "https://api.tweetscout.io/v2"
        self.input_file = input_file
        self.db_path = "followingA.db"  # 直接创建followingA.db，简化流程
        self.headers = {
            "ApiKey": api_key,
            "Accept": "application/json"
        }
        self.session = self._create_session()
        self._setup_logging()
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
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(name)s:%(funcName)s - %(message)s',
            handlers=[
                logging.FileHandler('getseedkol.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("GetSeedKOL")

    def _init_database(self):
        """初始化SQLite数据库 - 直接创建followingA.db"""
        # 备份旧数据库
        if os.path.exists(self.db_path):
            backup_path = f"{self.db_path}.{int(time.time())}.bak"
            os.rename(self.db_path, backup_path)
            self.logger.info(f"已备份现有数据库到 {backup_path}")
        
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # 创建users表 - 添加头像和背景图片字段
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                followers_count INTEGER,
                friends_count INTEGER,
                tweets_count INTEGER,
                avatar_url TEXT,
                banner_url TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_user_id ON users(user_id);
        ''')
        self.conn.commit()
        self.logger.info(f"初始化数据库 {self.db_path} 完成")

    def load_usernames(self) -> List[str]:
        """从文件加载KOL用户名"""
        if not self.input_file or not os.path.exists(self.input_file):
            self.logger.error(f"输入文件 {self.input_file} 不存在")
            return []
            
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                usernames = []
                
                if isinstance(data, list):
                    if data and isinstance(data[0], dict):
                        if 'username' in data[0]:
                            usernames = [user['username'] for user in data if 'username' in user]
                        else:
                            # 尝试找到用户名字段
                            username_fields = ['username', 'author_username', 'screen_name', 'handle']
                            for field in username_fields:
                                if field in data[0]:
                                    usernames = [user[field] for user in data if field in user]
                                    break
                            else:
                                if data[0]:
                                    self.logger.warning(f"无法识别用户名字段。可用字段: {list(data[0].keys())}")
                    else:
                        usernames = [u for u in data if isinstance(u, str)]
                
                self.logger.info(f"从 {self.input_file} 加载了 {len(usernames)} 个KOL用户名")
                return usernames
        except Exception as e:
            self.logger.error(f"加载用户名文件时出错: {str(e)}")
            return []

    def get_user_id(self, username: str) -> Optional[str]:
        """从Twitter用户名获取用户ID"""
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
                    self.logger.info(f"获取到 {username} 的用户ID: {data['id']}")
                    return data['id']
                else:
                    self.logger.warning(f"{username} 的响应中未找到ID")
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                self.logger.warning(f"达到速率限制。等待 {retry_after} 秒...")
                time.sleep(retry_after)
                return self.get_user_id(username)  # 等待后重试
            else:
                self.logger.error(f"获取 {username} 的用户ID失败: 状态 {response.status_code}, {response.text}")
                
        except Exception as e:
            self.logger.error(f"获取 {username} 的用户ID时出错: {str(e)}")
            
        return None

    def get_user_info(self, username: str) -> Dict[str, Any]:
        """通过用户名获取详细的用户信息"""
        try:
            url = f"{self.base_url}/info/{username}"
            
            response = self.session.get(
                url, 
                headers=self.headers,
                timeout=30
            )
            
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

    def get_user_info_by_id(self, user_id: str) -> Dict[str, Any]:
        """通过用户ID获取详细的用户信息"""
        try:
            url = f"{self.base_url}/info-id/{user_id}"
            
            response = self.session.get(
                url, 
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"获取到ID {user_id} 的用户信息")
                return data
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                self.logger.warning(f"达到速率限制。等待 {retry_after} 秒...")
                time.sleep(retry_after)
                return self.get_user_info_by_id(user_id)  # 等待后重试
            elif response.status_code == 404:
                self.logger.warning(f"用户ID {user_id} 未找到")
            else:
                self.logger.error(f"获取ID {user_id} 的用户信息失败: 状态 {response.status_code}, {response.text}")
                
        except Exception as e:
            self.logger.error(f"获取ID {user_id} 的用户信息时出错: {str(e)}")
            
        return {}


    def save_user(self, user_info: Dict[str, Any]) -> None:
        """将用户信息保存到数据库 - 添加头像和背景图片URL"""
        if not user_info or 'id' not in user_info:
            return

        try:
            # 获取头像URL - API返回的字段名是 'avatar'
            avatar_url = user_info.get('avatar', '')

            # 将小尺寸头像URL转换为大尺寸
            if avatar_url and '_normal.' in avatar_url:
                avatar_url = avatar_url.replace('_normal.', '_400x400.')

            # 获取背景图片URL - API返回的字段名是 'banner'
            banner_url = user_info.get('banner', '')

            self.logger.info(f"用户 {user_info.get('screen_name')} 的头像URL: {avatar_url}")
            self.logger.info(f"用户 {user_info.get('screen_name')} 的背景URL: {banner_url}")

            # 保存到数据库，包括头像和背景图片URL
            self.cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, followers_count, friends_count, tweets_count, avatar_url, banner_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_info.get('id'),
                user_info.get('screen_name'),
                user_info.get('followers_count', 0),
                user_info.get('friends_count', 0),
                user_info.get('tweets_count', 0),  # API返回的字段名是 'tweets_count'
                avatar_url,
                banner_url
            ))

            self.conn.commit()
            self.logger.info(f"保存了 {user_info.get('screen_name')} 的用户信息 (ID: {user_info.get('id')})")
        
        except sqlite3.Error as e:
            self.logger.error(f"保存用户时数据库错误: {str(e)}")
            self.conn.rollback()
        except Exception as e:
            self.logger.error(f"保存用户时出错: {str(e)}")
            self.conn.rollback()

    def process_username(self, username: str) -> None:
        """处理单个用户名以获取ID和信息"""
        try:
            self.logger.info(f"处理KOL用户名: {username}")
            
            # 直接通过用户名获取用户信息
            user_info = self.get_user_info(username)
            
            if user_info and 'id' in user_info:
                self.save_user(user_info)
            else:
                # 如果直接信息请求失败，先尝试获取用户ID
                user_id = self.get_user_id(username)
                if user_id:
                    user_info = self.get_user_info_by_id(user_id)
                    if user_info:
                        self.save_user(user_info)
                    else:
                        self.logger.warning(f"无法获取 {username} 的信息 (ID: {user_id})")
                else:
                    self.logger.warning(f"无法获取 {username} 的ID")
            
            # 请求之间添加小延迟
            time.sleep(1.5)  # 增加了延迟，避免API限流
                
        except Exception as e:
            self.logger.error(f"处理用户名 {username} 时出错: {str(e)}")

    def export_kol_list_json(self, output_file="kol_list.json"):
        """导出KOL列表为JSON格式，包含用户名、头像和背景图片URL"""
        try:
            self.logger.info(f"开始导出KOL列表到 {output_file}")
            
            # 从数据库中查询所有用户信息
            self.cursor.execute('''
                SELECT username, avatar_url, banner_url FROM users
            ''')
            
            users = []
            for row in self.cursor.fetchall():
                username, avatar_url, banner_url = row
                user_data = {
                    "username": username,
                    "avatar": avatar_url if avatar_url else "",
                    "background": banner_url if banner_url else ""
                }
                users.append(user_data)
            
            # 写入JSON文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"成功导出 {len(users)} 个KOL信息到 {output_file}")
            
        except Exception as e:
            self.logger.error(f"导出KOL列表时出错: {str(e)}")

    def run(self) -> None:
        """对所有KOL用户名运行爬虫"""
        try:
            usernames = self.load_usernames()
            if not usernames:
                self.logger.warning("未提供KOL用户名。退出。")
                return

            self.logger.info(f"开始处理 {len(usernames)} 个KOL用户名")

            for i, username in enumerate(usernames, 1):
                self.process_username(username)
                self.logger.info(f"已处理 {i}/{len(usernames)} 个KOL")

            # 导出为kol_list.json
            self.export_kol_list_json()
            
            self.logger.info("所有KOL用户信息已保存到数据库和JSON文件")

        except Exception as e:
            self.logger.error(f"主运行循环中出错: {str(e)}")

        finally:
            # 关闭连接
            if hasattr(self, 'conn') and self.conn:
                try:
                    self.conn.close()
                    self.logger.info("爬虫完成，数据库连接已关闭")
                except Exception as db_close_err:
                    self.logger.error(f"关闭数据库连接时出错: {db_close_err}")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="GetSeedKOL - 获取指定KOL信息")
    parser.add_argument("--input", required=True, help="输入JSON文件路径，包含KOL列表")
    args = parser.parse_args()
    
    # 使用命令行参数创建并运行爬虫
    crawler = GetSeedKOL(
        api_key="tweetscout api",  # 可以从环境变量获取
        input_file=args.input
    )
    
    crawler.run()

if __name__ == "__main__":
    main()