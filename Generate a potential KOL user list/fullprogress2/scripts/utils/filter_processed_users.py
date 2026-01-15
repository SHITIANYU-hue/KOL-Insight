#!/usr/bin/env python3
"""
filter_processed_users.py - Filter out users whose following lists have already been processed

这个脚本从following数据库中读取已经处理过的用户信息，并从twitter_users.json输入文件中过滤掉这些用户。
重要：只过滤真正爬取过following列表的用户，而不是简单地标记为processed的用户。

使用方法:
    python filter_processed_users.py --input data/input/twitter_users.json 
                                    --output data/input/twitter_users_filtered.json
                                    --db data/output/followingA.db
"""

import argparse
import json
import sqlite3
import os
import sys
import logging

def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('filter_processed_users.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('filter_processed_users')

def get_processed_users(db_path):
    """获取真正已经处理过following列表的用户ID集合
    
    通过检查following_relationships表中是否有用户的关注关系记录来判断
    一个用户是否真正被处理过，而不仅仅依赖processing_status表
    """
    if not os.path.exists(db_path):
        return set()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查following_relationships表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='following_relationships'")
        if not cursor.fetchone():
            logging.warning(f"数据库 {db_path} 中没有following_relationships表")
            conn.close()
            return set()
        
        # 获取在following_relationships表中作为following_of存在的用户ID
        # 这表示我们确实已经获取了这些用户的following列表
        cursor.execute("SELECT DISTINCT following_of FROM following_relationships")
        processed_users = {str(row[0]) for row in cursor.fetchall() if row[0]}
        
        # 记录找到的用户数量
        count = len(processed_users)
        conn.close()
        
        return processed_users
    
    except sqlite3.Error as e:
        logging.error(f"数据库错误: {e}")
        return set()

def filter_users(input_file, output_file, processed_users):
    """过滤掉已处理过的用户"""
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            users = json.load(f)
        
        initial_count = len(users)
        
        # 过滤掉已处理的用户
        # 这里检查用户ID或username是否在已处理集合中
        filtered_users = []
        for user in users:
            user_id = str(user.get('user_id', ''))
            if user_id and user_id in processed_users:
                continue
            filtered_users.append(user)
        
        filtered_count = len(filtered_users)
        removed_count = initial_count - filtered_count
        
        # 写入过滤后的列表到输出文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_users, f, indent=2, ensure_ascii=False)
        
        return initial_count, filtered_count, removed_count
    
    except Exception as e:
        logging.error(f"过滤用户时出错: {e}")
        return 0, 0, 0

def main():
    parser = argparse.ArgumentParser(description='从twitter_users.json中过滤掉已处理的用户')
    parser.add_argument('--input', required=True, help='输入JSON文件 (twitter_users.json)')
    parser.add_argument('--output', required=True, help='输出JSON文件 (过滤后的用户)')
    parser.add_argument('--db', required=True, help='包含已处理用户的数据库')
    
    args = parser.parse_args()
    logger = setup_logging()
    
    # 验证输入文件
    if not os.path.exists(args.input):
        logger.error(f"未找到输入文件: {args.input}")
        sys.exit(1)
    
    # 获取已处理的用户
    processed_users = get_processed_users(args.db)
    logger.info(f"在数据库中找到 {len(processed_users)} 个已经爬取过following的用户")
    
    # 过滤用户
    initial_count, filtered_count, removed_count = filter_users(
        args.input, args.output, processed_users
    )
    
    logger.info(f"初始用户数: {initial_count}")
    logger.info(f"过滤后用户数: {filtered_count}")
    logger.info(f"移除的用户数: {removed_count}")
    
    if removed_count > 0:
        logger.info(f"成功移除 {removed_count} 个已爬取过following的用户")
    else:
        logger.info("没有从输入文件中移除任何用户")

if __name__ == "__main__":
    main() 