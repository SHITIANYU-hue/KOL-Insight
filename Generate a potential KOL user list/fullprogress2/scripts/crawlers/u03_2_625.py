#!/usr/bin/env python3
"""u03_2.py  –  FollowingCrawler (阈值实时裁剪版本 + 排除已存在用户)

核心改动：
1. 在 get_user_following() 里，根据剩余缺口（max_threshold - self.total_valid_users）
   先行切片 filtered_following，确保返回数量不会超额。
2. 在 process_author() 保存循环中，每写一条就自增 self.total_valid_users，
   若已达阈值立即 break。
3. 删除原来一次性 += len(filtered_users) 的累计，避免双计。
4. 新增：排除followingA.db中已存在的用户，避免重复分析
"""

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
from typing import List, Dict, Any, Optional, Set
import argparse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class FollowingCrawler:
    def __init__(self, api_key, input_file=None, output_db=None, cycle=1, max_threshold=1000, following_threshold=3500, exclude_db=None):
        self.api_key = api_key
        self.input_file = input_file
        self.db_path = output_db if output_db else "following.db"
        self.cycle = cycle
        self.max_threshold = max_threshold
        self.following_threshold = following_threshold  # 新增：following数量阈值
        self.exclude_db = exclude_db  # 新增：排除数据库路径
        self.total_valid_users = 0
        
        # 新增：已存在用户ID集合，用于快速查找
        self.existing_user_ids: Set[str] = set()

        self.base_url = "https://api.tweetscout.io/v2"
        self.headers = {"ApiKey": api_key, "Accept": "application/json"}
        self.session = self._create_session()
        self._setup_logging()
        self.logger.info(f"初始化爬虫，循环次数: {cycle}, 输入文件: {input_file}, 输出数据库: {self.db_path}, following阈值: {following_threshold}")
        
        # 新增：加载已存在用户ID
        if self.exclude_db:
            self._load_existing_user_ids()
        
        # 不再进行API测试，直接初始化数据库
        self._init_database()

    # --- 新增方法：加载已存在用户ID ---
    def _load_existing_user_ids(self):
        """从排除数据库中加载已存在的用户ID到内存集合中，用于快速查找"""
        if not self.exclude_db or not os.path.exists(self.exclude_db):
            self.logger.warning(f"排除数据库不存在: {self.exclude_db}")
            return
        
        try:
            exclude_conn = sqlite3.connect(self.exclude_db)
            exclude_cursor = exclude_conn.cursor()
            
            # 检查users表是否存在
            exclude_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not exclude_cursor.fetchone():
                self.logger.warning(f"排除数据库中没有users表: {self.exclude_db}")
                exclude_conn.close()
                return
            
            # 加载所有已存在的user_id
            exclude_cursor.execute("SELECT user_id FROM users WHERE user_id IS NOT NULL")
            existing_ids = exclude_cursor.fetchall()
            
            self.existing_user_ids = {str(row[0]) for row in existing_ids if row[0]}
            exclude_conn.close()
            
            self.logger.info(f"从排除数据库 {self.exclude_db} 中加载了 {len(self.existing_user_ids):,} 个已存在用户ID")
            
        except sqlite3.Error as e:
            self.logger.error(f"加载排除数据库时出错: {e}")
            self.existing_user_ids = set()
    
    def _is_user_excluded(self, user_id: str) -> bool:
        """检查用户ID是否在排除列表中"""
        return str(user_id) in self.existing_user_ids
    
    def _filter_existing_users(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤掉已存在的用户"""
        if not self.existing_user_ids:
            return users
        
        filtered_users = []
        excluded_count = 0
        
        for user in users:
            user_id = user.get('id') or user.get('user_id')
            if not user_id:
                continue
                
            if not self._is_user_excluded(str(user_id)):
                filtered_users.append(user)
            else:
                excluded_count += 1
        
        if excluded_count > 0:
            self.logger.info(f"排除了 {excluded_count} 个已存在用户，剩余 {len(filtered_users)} 个新用户")
        
        return filtered_users

    # --- session / logging / db helpers ------------------------------------------------
    def _create_session(self):
        session = requests.Session()
        # 可以修改这里的total和backoff_factop值，前者限制最高重试次数，后者用于计算每次重试的时间间隔。
        # 时间间隔公式 第n次重试与上一次重试的时间间隔为n * backoff_factor秒
        retry_strategy = Retry(total=3, backoff_factor=1.5,
                               status_forcelist=[429,500,502,503,504],
                               allowed_methods=["GET","POST"],
                               respect_retry_after_header=True)
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=25, pool_block=True)
        session.mount("http://", adapter); session.mount("https://", adapter)
        session.verify = False
        return session

    def _setup_logging(self):
        logging.basicConfig(level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(name)s:%(funcName)s - %(message)s',
            handlers=[logging.FileHandler(f'crawler_cycle{self.cycle}.log'), logging.StreamHandler()])
        self.logger = logging.getLogger("FollowingCrawler")

    def _init_database(self):
        if os.path.exists(self.db_path):
            backup = f"{self.db_path}.{int(time.time())}.bak"; os.rename(self.db_path, backup)
            self.logger.info(f"Backed up existing database to {backup}")
        self.conn = sqlite3.connect(self.db_path); self.cursor = self.conn.cursor()
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                screen_name TEXT,
                description TEXT,
                followers_count INTEGER,
                friends_count INTEGER,
                tweets_count INTEGER,
                register_date TEXT,
                avatar TEXT,
                banner TEXT,
                verified BOOLEAN,
                can_dm BOOLEAN,
                processed BOOLEAN DEFAULT FALSE,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS following_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                following_of TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, following_of)
            );
            CREATE TABLE IF NOT EXISTS processing_status (
                user_id TEXT PRIMARY KEY, processed BOOLEAN DEFAULT FALSE, last_processed TIMESTAMP);
            CREATE INDEX IF NOT EXISTS idx_followers_count ON users(followers_count);
            CREATE INDEX IF NOT EXISTS idx_following_rel ON following_relationships(user_id, following_of);
        ''');
        self.conn.commit(); self.logger.info("数据库初始化完成")

    # --- core helpers ------------------------------------------------------------------
    def load_seed_users(self) -> List[Dict[str,Any]]:
        try:
            with open(self.input_file,'r',encoding='utf-8') as f:
                data=json.load(f)
                self.logger.info(f"从JSON文件加载了数据类型: {type(data)}, 长度: {len(data) if isinstance(data, list) else '未知'}")
                if isinstance(data, list) and len(data) > 0:
                    first_user = data[0]
                    self.logger.info(f"第一个用户数据: {json.dumps(first_user, ensure_ascii=False)}")
                return data if isinstance(data,list) else []
        except Exception as e:
            self.logger.error(f"加载种子用户文件错误: {e}")
            return []
    
    def load_users_from_db(self) -> List[Dict[str,Any]]:
        try:
            source_conn = sqlite3.connect(self.input_file)
            source_cursor = source_conn.cursor()
            source_cursor.execute("""
                SELECT user_id, username, followers_count 
                FROM users 
                ORDER BY followers_count DESC
                LIMIT 1000
            """)
            users = []
            for row in source_cursor.fetchall():
                users.append({
                    'user_id': row[0],
                    'username': row[1],
                    'followers_count': row[2]
                })
            source_conn.close()
            self.logger.info(f"从数据库 {self.input_file} 中读取了 {len(users)} 个用户")
            return users
        except sqlite3.Error as e:
            self.logger.error(f"读取数据库错误: {e}")
            return []

    def get_user_following(self, author: Dict[str,Any], retries: int = 3) -> List[Dict[str,Any]]:
        following = []
        retry_count = 0
        chunk_size = 100 # API可能会忽略这个限制并返回全部数据
        user_id = author.get('user_id')
        username = author.get('username', f"user_{user_id}")
        friends_count = author.get('friends_count', 0)
        
        # 根据following数量动态调整超时时间
        if friends_count > self.following_threshold:
            timeout = 60  # 高following用户使用较短超时
            self.logger.info(f"高following用户，使用较短超时时间: {timeout}秒")
        else:
            timeout = 120  # 普通用户使用正常超时
        
        if not user_id:
            self.logger.error(f"Author missing user_id: {author}")
            return []
            
        self.logger.info(f"开始获取用户 {username} (ID:{user_id}) 的following... (friends_count: {friends_count})")
        
        while retry_count < retries:
            try:
                self.logger.info(f"开始请求API, 尝试次数: {retry_count+1}/{retries}")
                request_url = f"{self.base_url}/follows"
                
                # 添加order_by=score参数可能会加快重要用户的获取
                params = {"user_id": user_id, "limit": chunk_size, "order_by": "score"}
                self.logger.info(f"请求URL: {request_url}, Params: {params}")
                
                # 请求超时时间降低为120秒，避免过长等待
                resp = self.session.get(request_url, headers=self.headers,
                                       params=params, timeout=timeout)
                
                self.logger.info(f"API响应状态码: {resp.status_code}")
                
                if resp.status_code == 200:
                    data = resp.json()
                    data_size = len(data) if isinstance(data, list) else 0
                    self.logger.info(f"成功获取数据，条目数: {data_size if data_size else '非列表数据'}")
                    
                    if isinstance(data, list) and data_size > 0:
                        following.extend(data)
                        
                        # 新增：先排除已存在用户
                        before_exclude_count = len(following)
                        following = self._filter_existing_users(following)
                        after_exclude_count = len(following)
                        excluded_count = before_exclude_count - after_exclude_count
                        
                        if excluded_count > 0:
                            self.logger.info(f"排除了 {excluded_count} 个已存在用户")
                        
                        # 然后按粉丝数过滤
                        filtered = [f for f in following if f.get('followers_count', 0) > 2000]
                        self.logger.info(f"过滤后following数量(>2000): {len(filtered)}/{len(following)}")
                        
                        # 预裁剪到剩余缺口
                        remain = self.max_threshold - self.total_valid_users
                        if remain > 0:
                            filtered = filtered[:remain]
                        else:
                            filtered = []
                        self.logger.info(f"Retrieved {len(filtered)} filtered following (>2000, 排除已存在) for {username} (remain {remain})")
                        return filtered
                    else:
                        self.logger.error(f"Unexpected response format or empty data")
                        return []
                elif resp.status_code in (429, 403):
                    retry_after = int(resp.headers.get('Retry-After', 60))
                    self.logger.warning(f"Rate limited {resp.status_code}. Sleep {retry_after}s…")
                    time.sleep(retry_after)
                    retry_count += 1
                elif resp.status_code == 404:
                    self.logger.error(f"资源不存在(404): {resp.text}")
                    return []  # 不再重试
                elif resp.status_code == 401:
                    self.logger.error(f"授权问题(401): {resp.text}")
                    return []  # 不再重试
                else:
                    self.logger.error(f"Failed with {resp.status_code}: {resp.text}")
                    retry_count += 1
                    # 指数退避策略
                    backoff_time = min(30, 5 * (2 ** retry_count))
                    self.logger.info(f"等待 {backoff_time} 秒后重试...")
                    time.sleep(backoff_time)
            except requests.exceptions.Timeout:
                self.logger.warning(f"请求超时，第{retry_count+1}次重试")
                retry_count += 1
                # 超时时增加较短的等待时间
                time.sleep(5)
            except Exception as e:
                self.logger.error(f"Error get_user_following: {e}")
                retry_count += 1
                time.sleep(10 * retry_count)
        
        self.logger.error(f"在{retries}次尝试后仍无法获取用户{username}的following数据")
        return []

    def save_following(self, user: Dict[str,Any], following_of:str):
        try:
            self.cursor.execute('''INSERT OR REPLACE INTO users (user_id,username,screen_name,description,followers_count,friends_count,tweets_count,register_date,avatar,banner,verified,can_dm,last_updated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',(
                user.get('id'), user.get('name'), user.get('screen_name'), user.get('description'),
                user.get('followers_count',0), user.get('friends_count',0), user.get('tweets_count',0),
                user.get('register_date'), user.get('avatar'), user.get('banner'), user.get('verified',False), user.get('can_dm',False)))
            self.cursor.execute('''INSERT OR IGNORE INTO following_relationships (user_id, following_of) VALUES (?,?)''',
                (user.get('id'), following_of))
            self.conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"DB error: {e}"); self.conn.rollback()
            
    def save_following_batch(self, users: List[Dict[str,Any]], following_of:str):
        """批量保存用户数据，减少数据库操作次数"""
        if not users:
            return 0
            
        try:
            # 开始一个事务
            self.conn.execute("BEGIN TRANSACTION")
            
            # 准备批量插入users表的数据
            users_data = [(
                user.get('id'), user.get('name'), user.get('screen_name'), user.get('description'),
                user.get('followers_count',0), user.get('friends_count',0), user.get('tweets_count',0),
                user.get('register_date'), user.get('avatar'), user.get('banner'), 
                user.get('verified',False), user.get('can_dm',False)
            ) for user in users if user.get('id')]
            
            # 批量插入users表
            self.cursor.executemany('''
                INSERT OR REPLACE INTO users 
                (user_id,username,screen_name,description,followers_count,friends_count,tweets_count,
                register_date,avatar,banner,verified,can_dm,last_updated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ''', users_data)
            
            # 准备批量插入following_relationships表的数据
            rel_data = [(user.get('id'), following_of) for user in users if user.get('id')]
            
            # 批量插入following_relationships表
            self.cursor.executemany('''
                INSERT OR IGNORE INTO following_relationships (user_id, following_of) 
                VALUES (?,?)
            ''', rel_data)
            
            # 提交事务
            self.conn.commit()
            return len(users_data)
        except sqlite3.Error as e:
            self.logger.error(f"批量保存数据库错误: {e}")
            self.conn.rollback()
            return 0

    def is_user_processed(self, uid):
        self.cursor.execute("SELECT processed FROM processing_status WHERE user_id=?", (uid,)); r=self.cursor.fetchone(); return r and r[0]
    def mark_user_processed(self, uid):
        self.cursor.execute("INSERT OR REPLACE INTO processing_status VALUES (?,TRUE,CURRENT_TIMESTAMP)", (uid,)); self.conn.commit()

    # --- main per-author ---------------------------------------------------------------
    def process_author(self, author:Dict[str,Any], force_process=False):
        uid = author['user_id']
        username = author.get('username', f"user_{uid}")  # 如果没有username，使用user_id作为替代
        friends_count = author.get('friends_count', 0)  # following数量
        
        if self.is_user_processed(uid):
            self.logger.info(f"用户 {uid} 已处理，跳过"); return 0
        
        # 检查following数量是否超过阈值（除非强制处理）
        if not force_process and friends_count > self.following_threshold:
            self.logger.warning(f"用户 {username} 的following数量({friends_count})超过阈值({self.following_threshold})，跳过处理")
            self.mark_user_processed(uid)
            return 0
            
        start_time = time.time()
        if friends_count > self.following_threshold:
            self.logger.info(f"强制处理高following用户: {username} (following: {friends_count})")
        else:
            self.logger.info(f"开始处理用户: {username} (following: {friends_count})")
        
        following_users = self.get_user_following(author)
        if not following_users:
            self.logger.info(f"未获取到任何符合条件的following用户，跳过处理")
            self.mark_user_processed(uid)
            return 0
            
        saved = 0
        batch_size = 50  # 每批处理的用户数
        batches = [following_users[i:i + batch_size] for i in range(0, len(following_users), batch_size)]
        
        self.logger.info(f"将{len(following_users)}个用户分为{len(batches)}批处理，每批{batch_size}个")
        
        for batch_idx, batch in enumerate(batches, 1):
            if self.total_valid_users >= self.max_threshold:
                self.logger.info(f"已达到阈值 {self.max_threshold}，停止保存多余用户"); break
                
            batch_start = time.time()
            self.logger.info(f"处理第{batch_idx}/{len(batches)}批用户...")
            
            # 计算当前批次能保存的最大数量，避免超过阈值
            available_slots = self.max_threshold - self.total_valid_users
            if available_slots <= 0:
                break
                
            # 如果批次大小超过可用槽位，则裁剪批次
            actual_batch = batch
            if len(batch) > available_slots:
                actual_batch = batch[:available_slots]
                self.logger.info(f"当前批次裁剪至{len(actual_batch)}个用户以避免超过阈值")
            
            # 使用批处理函数保存用户
            try:
                batch_saved = self.save_following_batch(actual_batch, username)
                if batch_saved > 0:
                    self.total_valid_users += batch_saved
                    saved += batch_saved
                    self.logger.info(f"批量保存成功，本批次新增{batch_saved}个用户")
            except Exception as e:
                self.logger.error(f"批量保存用户时出错: {e}")
            
            batch_end = time.time()
            batch_time = batch_end - batch_start
            avg_time = batch_time / len(actual_batch) if actual_batch else 0
            self.logger.info(f"第{batch_idx}批处理完成，耗时{batch_time:.2f}秒，平均每用户{avg_time:.4f}秒")
            
            # 批次间短暂休息，避免数据库锁争用
            if batch_idx < len(batches) and self.total_valid_users < self.max_threshold:
                time.sleep(0.5)
        
        self.mark_user_processed(uid)
        end_time = time.time()
        total_time = end_time - start_time
        self.logger.info(f"Completed author {username}, saved {saved} users (total_valid={self.total_valid_users}), 总耗时: {total_time:.2f}秒")
        return saved

    # --- run ---------------------------------------------------------------------------
    def run(self):
        self.logger.info(f"开始执行run方法，输入文件: {self.input_file}")
        if self.exclude_db:
            self.logger.info(f"排除数据库: {self.exclude_db}, 已加载 {len(self.existing_user_ids):,} 个已存在用户ID")
        
        start_time = time.time()
        
        # 加载种子用户
        if self.input_file.endswith('.json'):
            self.logger.info("检测到JSON输入文件，开始加载种子用户")
            authors = self.load_seed_users()
        elif self.input_file.endswith('.db'):
            self.logger.info("检测到DB输入文件，开始从数据库加载用户")
            authors = self.load_users_from_db()
        else:
            self.logger.error(f"不支持的输入文件格式: {self.input_file}")
            raise ValueError('仅支持 .json 或 .db 格式的输入文件')
        
        # 检查种子用户
        self.logger.info(f"加载了 {len(authors)} 个种子用户")
        if not authors:
            self.logger.warning("没有获取到种子用户，请检查输入文件")
            self.conn.close()
            return 0
            
        # 按照followers_count排序，优先处理follower数较多的用户
        authors.sort(key=lambda x: x.get('followers_count', 0), reverse=True)
        self.logger.info(f"已按followers_count降序排列作者")
        
        # 统计用户following数量分布
        low_following_users = [a for a in authors if a.get('friends_count', 0) <= self.following_threshold]
        high_following_users = [a for a in authors if a.get('friends_count', 0) > self.following_threshold]
        self.logger.info(f"用户分布：低following用户({len(low_following_users)})，高following用户({len(high_following_users)})")
        
        # 优先处理低following数量的用户
        priority_authors = low_following_users + high_following_users
        
        # 处理种子用户
        added = 0
        processed_count = 0
        skipped_high_following = 0
        
        for idx, a in enumerate(priority_authors, 1):
            username = a.get('username', a.get('user_id', '未知'))
            friends_count = a.get('friends_count', 0)
            
            self.logger.info(f"处理第 {idx}/{len(priority_authors)} 个作者: {username} (following: {friends_count})")
            
            if self.total_valid_users >= self.max_threshold: 
                self.logger.info(f"已达到阈值 {self.max_threshold}，停止处理更多作者")
                break
                
            # 智能跳过逻辑：如果是高following用户，检查是否还有其他选择
            if friends_count > self.following_threshold:
                remaining_low_following = len([u for u in priority_authors[idx:] if u.get('friends_count', 0) <= self.following_threshold])
                remaining_need = self.max_threshold - self.total_valid_users
                
                if remaining_low_following > 0:
                    self.logger.info(f"跳过高following用户 {username}，还有 {remaining_low_following} 个低following用户可处理")
                    skipped_high_following += 1
                    continue
                elif remaining_need > 0:
                    self.logger.info(f"没有更多低following用户，但还需要 {remaining_need} 个用户，处理高following用户 {username}")
                else:
                    self.logger.info(f"已达到目标，跳过高following用户 {username}")
                    continue
            
            try:
                # 判断是否需要强制处理高following用户
                force_process = friends_count > self.following_threshold
                current_added = self.process_author(a, force_process=force_process)
                added += current_added
                processed_count += 1
                self.logger.info(f"该作者新增了 {current_added} 个用户，当前总计: {self.total_valid_users}/{self.max_threshold}")
                
                # 定期提交数据库，避免长时间锁定
                self.conn.commit()
            except Exception as e:
                self.logger.error(f"处理作者时发生错误: {e}")
                self.conn.rollback()
                
        end_time = time.time()
        total_run_time = end_time - start_time
        self.logger.info(f"循环完成统计:")
        self.logger.info(f"  - 处理作者数: {processed_count}/{len(priority_authors)}")
        self.logger.info(f"  - 跳过高following用户: {skipped_high_following}")
        self.logger.info(f"  - 新增有效用户: {added}")
        self.logger.info(f"  - 总计有效用户: {self.total_valid_users}")
        if self.exclude_db:
            self.logger.info(f"  - 排除的已存在用户: {len(self.existing_user_ids):,}")
        self.logger.info(f"  - 总耗时: {total_run_time:.2f}秒")
        self.conn.close(); return added

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser=argparse.ArgumentParser();
    parser.add_argument('--input',required=True); parser.add_argument('--output',required=True);
    parser.add_argument('--cycle',type=int,required=True); parser.add_argument('--max_threshold',type=int,required=True)
    parser.add_argument('--following_threshold',type=int,default=3500, help='跳过following数量超过此阈值的用户 (默认3500)')
    parser.add_argument('--exclude_db', help='排除数据库路径，用于避免重复分析已存在用户')  # 新增参数
    args=parser.parse_args()
    crawler=FollowingCrawler(
        api_key="你的api", 
        input_file=args.input, 
        output_db=args.output, 
        cycle=args.cycle, 
        max_threshold=args.max_threshold, 
        following_threshold=args.following_threshold,
        exclude_db=args.exclude_db  # 新增参数
    )
    valid=crawler.run()
    with open('valid_users_count.txt','w') as f: f.write(str(valid))
    print(f"第{args.cycle}次循环完成，新增{valid}个有效用户")