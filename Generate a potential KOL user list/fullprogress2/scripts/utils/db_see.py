import sqlite3
import json

def inspect_database(db_path):
    """查看数据库结构和内容"""
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print(f"正在分析数据库: {db_path}")
        print("=" * 60)
        
        # 1. 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"发现 {len(tables)} 个表: {tables}")
        print()
        
        # 2. 分析每个表
        for table_name in tables:
            print(f"📋 表名: {table_name}")
            print("-" * 40)
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print("列信息:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]}) {'[主键]' if col[5] else ''}")
            
            # 获取记录数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"记录数: {count}")
            
            # 显示前3行数据
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            
            if rows:
                print("前3行数据:")
                for i, row in enumerate(rows, 1):
                    print(f"  第{i}行: {dict(row)}")
            
            print()
            print("=" * 60)
            print()
        
        conn.close()
        
    except Exception as e:
        print(f"错误: {e}")

# 使用示例
if __name__ == "__main__":
    # 修改这里的路径为你的数据库文件路径
    db_file = input("请输入数据库文件路径: ")
    inspect_database(db_file)