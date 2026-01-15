#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_kol_list.py - 从数据库读取KOL用户名并生成kol_list.json
"""

import sqlite3
import json
import argparse
import sys
import os
from pathlib import Path


def read_usernames_from_db(db_path, table_name=None, username_column='screen_name'):
    """
    从SQLite数据库中读取用户名
    
    Args:
        db_path: 数据库文件路径
        table_name: 表名（如果为None，会自动检测）
        username_column: 用户名列的名称
    
    Returns:
        list: 用户名列表
    """
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 如果没有指定表名，尝试自动检测
        if table_name is None:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            if not tables:
                print("❌ 数据库中没有找到任何表")
                return []
            
            # 优先选择包含 'kol', 'user', 'account' 等关键词的表
            preferred_keywords = ['kol', 'user', 'account', 'twitter']
            table_name = None
            
            for keyword in preferred_keywords:
                for table in tables:
                    if keyword.lower() in table[0].lower():
                        table_name = table[0]
                        break
                if table_name:
                    break
            
            # 如果没有找到匹配的表，使用第一个表
            if table_name is None:
                table_name = tables[0][0]
            
            print(f"🔍 自动检测到表: {table_name}")
        
        # 检查表中是否存在username列
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 尝试不同的可能的用户名列名，优先使用screen_name
        possible_username_columns = [username_column, 'screen_name', 'username', 'user_name', 'name', 'handle']
        actual_username_column = None
        
        for col in possible_username_columns:
            if col in columns:
                actual_username_column = col
                break
        
        if actual_username_column is None:
            print(f"❌ 在表 {table_name} 中没有找到用户名列")
            print(f"可用的列: {', '.join(columns)}")
            return []
        
        print(f"📊 使用列: {actual_username_column}")
        
        # 读取用户名
        query = f"SELECT DISTINCT {actual_username_column} FROM {table_name} WHERE {actual_username_column} IS NOT NULL AND {actual_username_column} != ''"
        cursor.execute(query)
        usernames = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        print(f"✅ 成功读取到 {len(usernames)} 个用户名")
        return usernames
        
    except sqlite3.Error as e:
        print(f"❌ 数据库操作错误: {e}")
        return []
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return []


def create_kol_list_json(usernames, output_path='kol_list.json'):
    """
    创建kol_list.json文件
    
    Args:
        usernames: 用户名列表
        output_path: 输出文件路径
    """
    if not usernames:
        print("❌ 没有用户名可以写入")
        return False
    
    try:
        # 创建KOL列表格式
        kol_list = [{"username": username} for username in usernames]
        
        # 写入JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(kol_list, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 成功创建 {output_path}，包含 {len(usernames)} 个KOL")
        return True
        
    except Exception as e:
        print(f"❌ 创建JSON文件失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='从数据库读取KOL用户名并生成kol_list.json')
    parser.add_argument('--db', '--database', default='KOL_yes.db', 
                       help='数据库文件路径 (默认: KOL_yes.db)')
    parser.add_argument('--table', default=None, 
                       help='表名 (如果不指定会自动检测)')
    parser.add_argument('--column', default='screen_name', 
                       help='用户名列名 (默认: screen_name)')
    parser.add_argument('--output', '-o', default='kol_list.json', 
                       help='输出文件路径 (默认: kol_list.json)')
    parser.add_argument('--limit', type=int, default=None, 
                       help='限制读取的用户名数量')
    
    args = parser.parse_args()
    
    print(f"📖 正在从数据库读取KOL列表: {args.db}")
    
    # 读取用户名
    usernames = read_usernames_from_db(args.db, args.table, args.column)
    
    if not usernames:
        print("❌ 没有读取到任何用户名")
        sys.exit(1)
    
    # 如果设置了限制，截取指定数量
    if args.limit and args.limit > 0:
        usernames = usernames[:args.limit]
        print(f"🔢 限制输出到前 {len(usernames)} 个用户名")
    
    # 创建JSON文件
    success = create_kol_list_json(usernames, args.output)
    
    if success:
        print(f"\n📋 生成的KOL列表预览:")
        for i, username in enumerate(usernames[:5], 1):  # 只显示前5个
            print(f"  {i}. {username}")
        if len(usernames) > 5:
            print(f"  ... 还有 {len(usernames) - 5} 个")
        
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()