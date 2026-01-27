#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合主程序：输入用户名 → 爬取数据 → 计算评分 → 生成评价网页

使用方法:
    python generate_report.py
    或者修改下面的 USERNAME 变量
"""

import os
import json
import sqlite3
import asyncio
from dataclasses import asdict
from pathlib import Path

from twitter_crawler import TwitterCrawler
from models.data_model import Account, Tweet
from scoring.engine import calculate, save_tree_structure
from scoring.schema import score_tree
from scoring.normalization_manager import NormalizationManager
from generate_static_html import generate_main_page, generate_user_page, read_json_file

# ==================== 配置 ====================
# 要分析的 Twitter 用户名（不含 @）
USERNAME = "elonmusk"  # 可以修改这里

# API 密钥（从环境变量获取）
TWEETSCOUT_API_KEY = os.getenv("TWEETSCOUT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 爬取配置
MAX_TWEETS = 50  # 每个用户最多爬取多少条推文
SKIP_COMMENTS = True  # 是否跳过评论（True 可以加快速度）

# 评分配置
TWEETS_LIMIT = 10  # 评分时每个账号只取前 N 条推文（防止 AI 调用过多）

# 输出目录
DATA_DIR = "data"
OUTPUT_DIR = "outputs"
STATIC_HTML_DIR = "static_html"
# ==============================================


def convert_twitter_db_to_scoring_format(twitter_db_path: str, username: str):
    """
    将 twitter_crawler 生成的数据库转换为评分系统需要的格式
    
    Args:
        twitter_db_path: twitter_crawler 生成的数据库路径
        username: 要处理的用户名
        
    Returns:
        (accounts, tweets): Account 和 Tweet 对象列表
    """
    if not os.path.exists(twitter_db_path):
        raise FileNotFoundError(f"数据库文件不存在: {twitter_db_path}")
    
    conn = sqlite3.connect(twitter_db_path)
    cursor = conn.cursor()
    
    # 从 users 表读取用户信息
    cursor.execute("SELECT user_id, username, followers_count, friends_count, tweets_count, avatar_url, banner_url FROM users WHERE username = ?", (username,))
    user_row = cursor.fetchone()
    
    if not user_row:
        conn.close()
        raise ValueError(f"未找到用户: {username}")
    
    user_id, username_db, followers_count, friends_count, tweets_count, avatar_url, banner_url = user_row
    
    # 从 tweets 表读取推文（读取所有推文，后续会在评分时限制）
    cursor.execute("""
        SELECT tweet_id, conversation_id, author_id, author_name, full_text, created_at,
               likes_count, retweets_count, replies_count, views_count,
               in_reply_to_status_id_str, is_quote_status
        FROM tweets 
        WHERE author_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    
    tweet_rows = cursor.fetchall()
    conn.close()
    
    # 转换为 Tweet 对象
    all_tweets = []
    for row in tweet_rows:
        tweet = Tweet(
            tweet_id=row[0] or "",
            author_id=row[2] or "",
            full_text=row[4] or "",
            likes_count=row[6] or 0,
            retweets_count=row[7] or 0,
            replies_count=row[8] or 0,
            views_count=row[9] or 0,
            in_reply_to_status_id_str=row[10] if len(row) > 10 else None,
            is_quote_status=row[11] if len(row) > 11 else 0
        )
        all_tweets.append(tweet)
    
    # 限制推文数量（防止 AI 调用过多）- 只用于评分
    tweets_for_scoring = all_tweets[:TWEETS_LIMIT] if len(all_tweets) > TWEETS_LIMIT else all_tweets
    
    # 创建 Account 对象
    # 注意：twitter_crawler 的 users 表没有 description 字段，使用默认值
    account = Account(
        user_id=user_id,
        username=username_db,
        description="",  # twitter_crawler 没有这个字段，使用空字符串
        followers_count=followers_count or 0,
        friends_count=friends_count or 0,
        tweets_count=tweets_count or 0,
        tweets=tweets_for_scoring  # 只使用限制后的推文进行评分
    )
    
    return [account], all_tweets  # 返回所有推文用于保存，但评分只用限制后的


def main():
    """主函数"""
    print("=" * 60)
    print("KOL 评价报告生成器")
    print("=" * 60)
    print(f"目标用户: @{USERNAME}")
    print()
    
    # 检查 API 密钥
    if not TWEETSCOUT_API_KEY:
        print("❌ 错误: 未设置 TWEETSCOUT_API_KEY 环境变量")
        print("   请设置: export TWEETSCOUT_API_KEY='your-key'")
        return 1
    
    if not OPENAI_API_KEY:
        print("⚠️  警告: 未设置 OPENAI_API_KEY 环境变量")
        print("   评分功能需要 OpenAI API，请设置: export OPENAI_API_KEY='your-key'")
        print("   继续执行...")
    
    # 确保目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(STATIC_HTML_DIR, exist_ok=True)
    
    twitter_db_path = os.path.join(DATA_DIR, "twitter_data.db")
    
    # ==================== 步骤 1: 爬取数据 ====================
    print("\n[步骤 1/4] 爬取 Twitter 数据...")
    print("-" * 60)
    
    crawler = TwitterCrawler(
        api_key=TWEETSCOUT_API_KEY,
        output_dir=DATA_DIR,
        db_name="twitter_data.db"
    )
    
    try:
        result = crawler.crawl_user(
            username=USERNAME,
            max_tweets=MAX_TWEETS,
            skip_comments=SKIP_COMMENTS
        )
        
        if not result or result.get('tweets_crawled', 0) == 0:
            print(f"❌ 未能爬取到 {USERNAME} 的推文数据")
            return 1
        
        print(f"✅ 爬取完成:")
        print(f"   推文数: {result['tweets_crawled']}")
        print(f"   耗时: {result['elapsed_time']:.2f} 秒")
        
    except Exception as e:
        print(f"❌ 爬取失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        crawler.close()
    
    # ==================== 步骤 2: 转换数据格式 ====================
    print("\n[步骤 2/4] 转换数据格式...")
    print("-" * 60)
    
    try:
        accounts, all_tweets = convert_twitter_db_to_scoring_format(twitter_db_path, USERNAME)
        
        if not accounts or len(accounts) == 0:
            print(f"❌ 未找到用户数据: {USERNAME}")
            return 1
        
        account = accounts[0]
        print(f"✅ 数据转换完成:")
        print(f"   用户: {account.username}")
        print(f"   粉丝数: {account.followers_count:,}")
        print(f"   推文数: {len(account.tweets)} (用于评分)")
        
        if len(account.tweets) == 0:
            print(f"⚠️  警告: 该用户没有推文数据，无法计算评分")
            return 1
        
    except Exception as e:
        print(f"❌ 数据转换失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # ==================== 步骤 3: 计算评分 ====================
    print("\n[步骤 3/4] 计算评分（这可能需要一些时间，因为需要调用 AI API）...")
    print("-" * 60)
    print(f"注意: 只使用前 {TWEETS_LIMIT} 条推文进行计算，防止 AI 调用过多")
    
    # 初始化归一化管理器（会自动加载已有的归一化参数）
    norm_manager = NormalizationManager()
    norm_manager.load_normalization_params()
    
    try:
        result = asyncio.run(calculate(accounts, score_tree, 
                                      normalization_manager=norm_manager,
                                      save_history=True))
        
        # 保存数据
        with open(os.path.join(OUTPUT_DIR, "accounts.json"), "w", encoding="utf-8") as f:
            json.dump([asdict(account) for account in accounts], f, ensure_ascii=False, indent=2)
        
        with open(os.path.join(OUTPUT_DIR, "tweets.json"), "w", encoding="utf-8") as f:
            json.dump([asdict(tweet) for tweet in all_tweets], f, ensure_ascii=False, indent=2)
        
        with open(os.path.join(OUTPUT_DIR, "scores.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        save_tree_structure(score_tree, os.path.join(OUTPUT_DIR, "tree_structure.json"))
        
        print("✅ 评分计算完成:")
        print(f"   账户数据已保存到: {OUTPUT_DIR}/accounts.json")
        print(f"   推文数据已保存到: {OUTPUT_DIR}/tweets.json")
        print(f"   评分数据已保存到: {OUTPUT_DIR}/scores.json")
        print(f"   评分树结构已保存到: {OUTPUT_DIR}/tree_structure.json")
        
        # 显示总分
        scores = result.get('scores', {})
        root_score = scores.get('root', [0])[0] if scores.get('root') else 0
        print(f"   综合评分: {root_score:.2%}")
        
    except Exception as e:
        print(f"❌ 评分计算失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # ==================== 步骤 4: 生成 HTML 网页 ====================
    print("\n[步骤 4/4] 生成评价网页...")
    print("-" * 60)
    
    try:
        # 读取数据
        accounts_data = read_json_file(os.path.join(OUTPUT_DIR, "accounts.json"))
        scores_data = read_json_file(os.path.join(OUTPUT_DIR, "scores.json"))
        tree_structure = read_json_file(os.path.join(OUTPUT_DIR, "tree_structure.json"))
        
        scores = scores_data.get('scores', scores_data)
        comments = scores_data.get('comments', {})
        
        # 生成主页面
        main_html = generate_main_page(accounts_data, scores, tree_structure)
        with open(os.path.join(STATIC_HTML_DIR, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(main_html)
        print(f"✅ 已生成主页面: {STATIC_HTML_DIR}/index.html")
        
        # 生成用户详细页面
        for i, account in enumerate(accounts_data):
            user_html = generate_user_page(account, scores, comments, tree_structure, i)
            filename = f'user_{i}.html'
            with open(os.path.join(STATIC_HTML_DIR, filename), 'w', encoding='utf-8') as f:
                f.write(user_html)
            username = account.get('username', '未知')
            print(f"✅ 已生成用户页面: {STATIC_HTML_DIR}/{filename} (用户: {username})")
        
        print()
        print("=" * 60)
        print("✅ 完成！")
        print("=" * 60)
        print(f"📄 评价网页已生成到: {os.path.abspath(STATIC_HTML_DIR)}/")
        print(f"   主页面: {STATIC_HTML_DIR}/index.html")
        print(f"   用户报告: {STATIC_HTML_DIR}/user_0.html")
        print()
        print("💡 提示: 可以直接在浏览器中打开 HTML 文件查看")
        
    except Exception as e:
        print(f"❌ 生成网页失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

