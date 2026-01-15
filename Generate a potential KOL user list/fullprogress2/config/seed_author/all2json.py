#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

class UniversalUsernameExtractor:
    def __init__(self):
        """初始化通用用户名提取器"""
        self.output_dir = "seed_author"
        self.ensure_output_dir()
        
    def ensure_output_dir(self):
        """确保输出目录存在"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"✅ 创建目录: {self.output_dir}")
    
    def get_timestamp(self) -> str:
        """获取时间戳"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def save_usernames(self, usernames: List[str], source_type: str) -> str:
        """保存用户名到JSON文件"""
        timestamp = self.get_timestamp()
        filename = f"{self.output_dir}/usernames_{source_type}_{timestamp}.json"
        
        # 转换为目标格式
        result = [{"username": username} for username in usernames if username.strip()]
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 成功提取 {len(result)} 个用户名")
        print(f"✅ 已保存到: {filename}")
        
        # 显示前5个结果预览
        print(f"\n📄 前5个结果预览:")
        for i, user in enumerate(result[:5], 1):
            print(f"  {i}. {user}")
        
        if len(result) > 5:
            print(f"  ... 还有 {len(result) - 5} 个")
        
        return filename
    
    def extract_from_txt(self, file_path: str) -> List[str]:
        """从TXT文件提取用户名"""
        try:
            print(f"正在读取TXT文件: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 清理每行数据，去除空白字符
            usernames = []
            for line in lines:
                username = line.strip()
                if username and not username.startswith('#'):  # 支持#注释
                    usernames.append(username)
            
            print(f"📊 从TXT文件读取到 {len(usernames)} 个用户名")
            return usernames
            
        except Exception as e:
            print(f"❌ 读取TXT文件失败: {e}")
            return []
    
    def extract_from_json(self, file_path: str) -> List[str]:
        """从JSON文件提取用户名"""
        try:
            print(f"正在读取JSON文件: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 分析JSON结构
            if isinstance(data, list):
                if len(data) > 0:
                    first_item = data[0]
                    if isinstance(first_item, str):
                        # 直接是字符串数组
                        print("📊 检测到字符串数组格式")
                        return [item for item in data if isinstance(item, str)]
                    
                    elif isinstance(first_item, dict):
                        # 对象数组，需要选择键
                        keys = list(first_item.keys())
                        print(f"📊 检测到对象数组，可用的键: {keys}")
                        
                        print("请选择要提取的键:")
                        for i, key in enumerate(keys, 1):
                            # 显示前3个值作为示例
                            sample_values = [str(item.get(key, '')) for item in data[:3] if item.get(key)]
                            print(f"  {i}. {key} - 示例: {sample_values}")
                        
                        choice = input(f"\n请选择 (1-{len(keys)}): ").strip()
                        try:
                            selected_key = keys[int(choice) - 1]
                            usernames = [str(item.get(selected_key, '')) for item in data if item.get(selected_key)]
                            print(f"✅ 选择了键: {selected_key}")
                            return usernames
                        except (ValueError, IndexError):
                            print("❌ 无效选择")
                            return []
            
            elif isinstance(data, dict):
                # 直接是对象
                keys = list(data.keys())
                print(f"📊 检测到单个对象，可用的键: {keys}")
                
                print("请选择要提取的键:")
                for i, key in enumerate(keys, 1):
                    value = data[key]
                    if isinstance(value, list):
                        print(f"  {i}. {key} - 数组，长度: {len(value)}")
                    else:
                        print(f"  {i}. {key} - 值: {str(value)[:50]}...")
                
                choice = input(f"\n请选择 (1-{len(keys)}): ").strip()
                try:
                    selected_key = keys[int(choice) - 1]
                    value = data[selected_key]
                    
                    if isinstance(value, list):
                        return [str(item) for item in value if item]
                    else:
                        return [str(value)] if value else []
                        
                except (ValueError, IndexError):
                    print("❌ 无效选择")
                    return []
            
            print("❌ 无法识别的JSON格式")
            return []
            
        except Exception as e:
            print(f"❌ 读取JSON文件失败: {e}")
            return []
    
    def extract_from_db(self, file_path: str) -> List[str]:
        """从数据库文件提取用户名"""
        try:
            print(f"正在读取数据库文件: {file_path}")
            
            conn = sqlite3.connect(file_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            
            if not tables:
                print("❌ 数据库中没有找到用户表")
                return []
            
            print(f"📊 找到 {len(tables)} 个表: {tables}")
            
            # 选择表
            if len(tables) == 1:
                selected_table = tables[0]
                print(f"✅ 自动选择表: {selected_table}")
            else:
                print("请选择表:")
                for i, table in enumerate(tables, 1):
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"  {i}. {table} ({count} 条记录)")
                
                choice = input(f"\n请选择 (1-{len(tables)}): ").strip()
                try:
                    selected_table = tables[int(choice) - 1]
                except (ValueError, IndexError):
                    print("❌ 无效选择")
                    return []
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({selected_table})")
            columns = [row[1] for row in cursor.fetchall()]
            
            print(f"📊 表 {selected_table} 的列: {columns}")
            
            # 显示列的示例数据
            cursor.execute(f"SELECT * FROM {selected_table} LIMIT 3")
            sample_rows = cursor.fetchall()
            
            print("列数据预览:")
            for col in columns:
                sample_values = [str(row[col]) for row in sample_rows if row[col]]
                print(f"  • {col}: {sample_values}")
            
            # 选择列
            print(f"\n请选择要提取的列:")
            for i, col in enumerate(columns, 1):
                print(f"  {i}. {col}")
            
            choice = input(f"\n请选择 (1-{len(columns)}): ").strip()
            try:
                selected_column = columns[int(choice) - 1]
            except (ValueError, IndexError):
                print("❌ 无效选择")
                return []
            
            # 提取数据
            query = f"SELECT {selected_column} FROM {selected_table} WHERE {selected_column} IS NOT NULL AND {selected_column} != ''"
            cursor.execute(query)
            rows = cursor.fetchall()
            
            usernames = [str(row[0]) for row in rows if row[0]]
            
            conn.close()
            print(f"✅ 从数据库提取到 {len(usernames)} 个用户名")
            return usernames
            
        except Exception as e:
            print(f"❌ 读取数据库文件失败: {e}")
            return []
    
    def manual_input(self) -> List[str]:
        """手动输入用户名"""
        print("📝 手动输入模式")
        print("请输入用户名，每行一个，输入空行结束:")
        print("(可以粘贴多行文本)")
        
        usernames = []
        while True:
            try:
                line = input().strip()
                if not line:
                    break
                usernames.append(line)
            except KeyboardInterrupt:
                print("\n⚠️ 输入被中断")
                break
        
        print(f"✅ 手动输入了 {len(usernames)} 个用户名")
        return usernames
    
    def detect_file_type(self, file_path: str) -> Optional[str]:
        """检测文件类型"""
        if not os.path.exists(file_path):
            return None
        
        _, ext = os.path.splitext(file_path.lower())
        
        if ext in ['.txt', '.text']:
            return 'txt'
        elif ext in ['.json']:
            return 'json'
        elif ext in ['.db', '.sqlite', '.sqlite3']:
            return 'db'
        else:
            return 'unknown'
    
    def run(self):
        """主运行函数"""
        print("🚀 通用用户名提取工具")
        print("=" * 60)
        print("支持的输入方式:")
        print("1. TXT文件 (每行一个用户名)")
        print("2. JSON文件 (自动识别结构)")
        print("3. 数据库文件 (SQLite)")
        print("4. 手动输入")
        print("=" * 60)
        
        while True:
            choice = input("\n请选择输入方式 (1-4) 或输入文件路径: ").strip()
            
            if not choice:
                print("👋 再见!")
                break
            
            usernames = []
            source_type = ""
            
            if choice in ['1', '2', '3', '4']:
                if choice == '1':
                    file_path = input("请输入TXT文件路径: ").strip()
                    if os.path.exists(file_path):
                        usernames = self.extract_from_txt(file_path)
                        source_type = "txt"
                    else:
                        print(f"❌ 文件不存在: {file_path}")
                        continue
                        
                elif choice == '2':
                    file_path = input("请输入JSON文件路径: ").strip()
                    if os.path.exists(file_path):
                        usernames = self.extract_from_json(file_path)
                        source_type = "json"
                    else:
                        print(f"❌ 文件不存在: {file_path}")
                        continue
                        
                elif choice == '3':
                    file_path = input("请输入数据库文件路径: ").strip()
                    if os.path.exists(file_path):
                        usernames = self.extract_from_db(file_path)
                        source_type = "db"
                    else:
                        print(f"❌ 文件不存在: {file_path}")
                        continue
                        
                elif choice == '4':
                    usernames = self.manual_input()
                    source_type = "manual"
            
            else:
                # 直接输入文件路径
                file_path = choice
                file_type = self.detect_file_type(file_path)
                
                if file_type is None:
                    print(f"❌ 文件不存在: {file_path}")
                    continue
                
                if file_type == 'txt':
                    usernames = self.extract_from_txt(file_path)
                    source_type = "txt"
                elif file_type == 'json':
                    usernames = self.extract_from_json(file_path)
                    source_type = "json"
                elif file_type == 'db':
                    usernames = self.extract_from_db(file_path)
                    source_type = "db"
                else:
                    print(f"❌ 不支持的文件类型: {file_type}")
                    print("支持的格式: .txt, .json, .db, .sqlite, .sqlite3")
                    continue
            
            # 保存结果
            if usernames:
                self.save_usernames(usernames, source_type)
            else:
                print("⚠️ 没有提取到任何用户名")
            
            # 询问是否继续
            continue_choice = input("\n是否继续提取? (y/n): ").strip().lower()
            if continue_choice not in ['y', 'yes', '是']:
                print("👋 再见!")
                break


if __name__ == "__main__":
    extractor = UniversalUsernameExtractor()
    extractor.run()