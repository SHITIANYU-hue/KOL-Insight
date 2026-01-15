#!/usr/bin/env python3
"""
数据库结构查看工具
用于分析SQLite数据库的表结构、数据内容和统计信息
"""

import sqlite3
import json
from typing import List, Dict, Any
import argparse
import os

class DatabaseInspector:
    def __init__(self, db_path: str):
        self.db_path = db_path
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")
        
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
    
    def get_table_list(self) -> List[str]:
        """获取数据库中所有表名"""
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in self.cursor.fetchall()]
        return tables
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表的结构信息"""
        self.cursor.execute(f"PRAGMA table_info({table_name});")
        columns = []
        for row in self.cursor.fetchall():
            columns.append({
                'cid': row[0],          # 列ID
                'name': row[1],         # 列名
                'type': row[2],         # 数据类型
                'notnull': row[3],      # 是否非空
                'default': row[4],      # 默认值
                'primary_key': row[5]   # 是否主键
            })
        return columns
    
    def get_table_count(self, table_name: str) -> int:
        """获取表的记录数"""
        self.cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        return self.cursor.fetchone()[0]
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取表的示例数据"""
        # 先获取列名
        columns = [col['name'] for col in self.get_table_schema(table_name)]
        
        # 获取示例数据
        self.cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
        rows = self.cursor.fetchall()
        
        # 转换为字典格式
        sample_data = []
        for row in rows:
            data_dict = {}
            for i, value in enumerate(row):
                data_dict[columns[i]] = value
            sample_data.append(data_dict)
        
        return sample_data
    
    def get_index_info(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表的索引信息"""
        self.cursor.execute(f"PRAGMA index_list({table_name});")
        indexes = []
        for row in self.cursor.fetchall():
            index_name = row[1]
            # 获取索引的详细信息
            self.cursor.execute(f"PRAGMA index_info({index_name});")
            index_columns = [col[2] for col in self.cursor.fetchall()]
            
            indexes.append({
                'name': index_name,
                'unique': bool(row[2]),
                'columns': index_columns
            })
        return indexes
    
    def analyze_users_table(self) -> Dict[str, Any]:
        """专门分析users表的数据分布"""
        if 'users' not in self.get_table_list():
            return {"error": "users表不存在"}
        
        analysis = {}
        
        # 基本统计
        analysis['total_users'] = self.get_table_count('users')
        
        # followers_count分布
        self.cursor.execute("""
            SELECT 
                MIN(followers_count) as min_followers,
                MAX(followers_count) as max_followers,
                AVG(followers_count) as avg_followers,
                COUNT(CASE WHEN followers_count > 2000 THEN 1 END) as users_over_2k,
                COUNT(CASE WHEN followers_count > 10000 THEN 1 END) as users_over_10k,
                COUNT(CASE WHEN followers_count > 100000 THEN 1 END) as users_over_100k
            FROM users 
            WHERE followers_count IS NOT NULL
        """)
        stats = self.cursor.fetchone()
        if stats:
            analysis['followers_stats'] = {
                'min': stats[0],
                'max': stats[1], 
                'avg': round(stats[2], 2) if stats[2] else 0,
                'over_2k': stats[3],
                'over_10k': stats[4],
                'over_100k': stats[5]
            }
        
        # 验证用户统计
        self.cursor.execute("SELECT COUNT(*) FROM users WHERE verified = 1")
        analysis['verified_users'] = self.cursor.fetchone()[0]
        
        # 获取top用户
        self.cursor.execute("""
            SELECT user_id, username, followers_count, verified 
            FROM users 
            ORDER BY followers_count DESC 
            LIMIT 10
        """)
        top_users = []
        for row in self.cursor.fetchall():
            top_users.append({
                'user_id': row[0],
                'username': row[1],
                'followers_count': row[2],
                'verified': bool(row[3])
            })
        analysis['top_users'] = top_users
        
        return analysis
    
    def analyze_relationships_table(self) -> Dict[str, Any]:
        """分析following_relationships表"""
        if 'following_relationships' not in self.get_table_list():
            return {"error": "following_relationships表不存在"}
        
        analysis = {}
        
        # 基本统计
        analysis['total_relationships'] = self.get_table_count('following_relationships')
        
        # 每个following_of的关注数统计
        self.cursor.execute("""
            SELECT 
                following_of,
                COUNT(*) as following_count
            FROM following_relationships 
            GROUP BY following_of 
            ORDER BY following_count DESC 
            LIMIT 10
        """)
        
        top_followings = []
        for row in self.cursor.fetchall():
            top_followings.append({
                'following_of': row[0],
                'following_count': row[1]
            })
        analysis['top_following_sources'] = top_followings
        
        # 获取唯一的following_of数量
        self.cursor.execute("SELECT COUNT(DISTINCT following_of) FROM following_relationships")
        analysis['unique_following_sources'] = self.cursor.fetchone()[0]
        
        # 获取唯一的user_id数量
        self.cursor.execute("SELECT COUNT(DISTINCT user_id) FROM following_relationships") 
        analysis['unique_followed_users'] = self.cursor.fetchone()[0]
        
        return analysis
    
    def generate_report(self) -> Dict[str, Any]:
        """生成完整的数据库分析报告"""
        report = {
            'database_path': self.db_path,
            'file_size_mb': round(os.path.getsize(self.db_path) / (1024*1024), 2),
            'tables': {}
        }
        
        tables = self.get_table_list()
        report['table_list'] = tables
        
        for table in tables:
            table_info = {
                'schema': self.get_table_schema(table),
                'record_count': self.get_table_count(table),
                'sample_data': self.get_sample_data(table, 3),
                'indexes': self.get_index_info(table)
            }
            report['tables'][table] = table_info
        
        # 特殊分析
        if 'users' in tables:
            report['users_analysis'] = self.analyze_users_table()
        
        if 'following_relationships' in tables:
            report['relationships_analysis'] = self.analyze_relationships_table()
        
        return report
    
    def print_summary(self):
        """打印数据库摘要信息"""
        print(f"\n📊 数据库分析报告: {self.db_path}")
        print("=" * 60)
        
        # 文件信息
        file_size = os.path.getsize(self.db_path) / (1024*1024)
        print(f"📁 文件大小: {file_size:.2f} MB")
        
        # 表信息
        tables = self.get_table_list()
        print(f"\n📋 表数量: {len(tables)}")
        
        for table in tables:
            count = self.get_table_count(table)
            print(f"  • {table}: {count:,} 条记录")
        
        # users表分析
        if 'users' in tables:
            print(f"\n👥 用户表分析:")
            analysis = self.analyze_users_table()
            if 'followers_stats' in analysis:
                stats = analysis['followers_stats']
                print(f"  • 总用户数: {analysis['total_users']:,}")
                print(f"  • 粉丝数范围: {stats['min']:,} - {stats['max']:,}")
                print(f"  • 平均粉丝数: {stats['avg']:,}")
                print(f"  • 粉丝>2K用户: {stats['over_2k']:,} ({stats['over_2k']/analysis['total_users']*100:.1f}%)")
                print(f"  • 粉丝>10K用户: {stats['over_10k']:,}")
                print(f"  • 粉丝>100K用户: {stats['over_100k']:,}")
                print(f"  • 认证用户: {analysis['verified_users']:,}")
        
        # 关注关系分析
        if 'following_relationships' in tables:
            print(f"\n🔗 关注关系分析:")
            analysis = self.analyze_relationships_table()
            print(f"  • 总关注关系: {analysis['total_relationships']:,}")
            print(f"  • 种子用户数: {analysis['unique_following_sources']:,}")
            print(f"  • 被关注用户数: {analysis['unique_followed_users']:,}")
    
    def close(self):
        """关闭数据库连接"""
        self.conn.close()

def main():
    parser = argparse.ArgumentParser(description='SQLite数据库结构分析工具')
    parser.add_argument('db_path', help='数据库文件路径')
    parser.add_argument('--detailed', '-d', action='store_true', help='显示详细信息')
    parser.add_argument('--export-json', '-j', help='导出完整报告到JSON文件')
    parser.add_argument('--table', '-t', help='只分析指定表')
    
    args = parser.parse_args()
    
    try:
        inspector = DatabaseInspector(args.db_path)
        
        if args.table:
            # 只分析指定表
            if args.table in inspector.get_table_list():
                print(f"\n📋 表 '{args.table}' 详细信息:")
                print("-" * 40)
                
                # 表结构
                print("\n🏗️  表结构:")
                schema = inspector.get_table_schema(args.table)
                for col in schema:
                    pk_mark = " (PK)" if col['primary_key'] else ""
                    notnull_mark = " NOT NULL" if col['notnull'] else ""
                    print(f"  • {col['name']}: {col['type']}{pk_mark}{notnull_mark}")
                
                # 记录数
                count = inspector.get_table_count(args.table)
                print(f"\n📊 记录数: {count:,}")
                
                # 示例数据
                if args.detailed:
                    print(f"\n📄 示例数据:")
                    sample_data = inspector.get_sample_data(args.table)
                    for i, record in enumerate(sample_data, 1):
                        print(f"\n  记录 {i}:")
                        for key, value in record.items():
                            print(f"    {key}: {value}")
            else:
                print(f"❌ 表 '{args.table}' 不存在")
                print(f"可用表: {', '.join(inspector.get_table_list())}")
        else:
            # 完整分析
            inspector.print_summary()
            
            if args.detailed:
                print(f"\n📋 详细表结构:")
                tables = inspector.get_table_list()
                for table in tables:
                    print(f"\n  表: {table}")
                    schema = inspector.get_table_schema(table)
                    for col in schema:
                        pk_mark = " (主键)" if col['primary_key'] else ""
                        notnull_mark = " 非空" if col['notnull'] else ""
                        default_mark = f" 默认:{col['default']}" if col['default'] else ""
                        print(f"    • {col['name']}: {col['type']}{pk_mark}{notnull_mark}{default_mark}")
        
        # 导出JSON报告
        if args.export_json:
            report = inspector.generate_report()
            with open(args.export_json, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\n💾 详细报告已导出到: {args.export_json}")
        
        inspector.close()
        
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}")
    except Exception as e:
        print(f"❌ 未知错误: {e}")

if __name__ == "__main__":
    main()