#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KOL 评价报告生成器 - Web 服务
提供 Web 界面，输入用户名即可自动爬取、评分并生成报告
"""

import os
import json
import sqlite3
import asyncio
import threading
from dataclasses import asdict
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS

from twitter_crawler import TwitterCrawler
from models.data_model import Account, Tweet
from scoring.engine import calculate, save_tree_structure
from scoring.schema import score_tree
from scoring.normalization_manager import NormalizationManager
from generate_static_html import generate_main_page, generate_user_page, read_json_file

app = Flask(__name__)
CORS(app)

# 配置
DATA_DIR = "data"
OUTPUT_DIR = "outputs"
STATIC_HTML_DIR = "static_html"
MAX_TWEETS = 50
SKIP_COMMENTS = True
TWEETS_LIMIT = 10

# 确保必要的目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_HTML_DIR, exist_ok=True)
os.makedirs('templates', exist_ok=True)

# 任务状态存储（简单实现，生产环境应使用Redis等）
tasks = {}


def convert_twitter_db_to_scoring_format(twitter_db_path: str, username: str):
    """
    将 twitter_crawler 生成的数据库转换为评分系统需要的格式
    """
    conn = sqlite3.connect(twitter_db_path)
    cursor = conn.cursor()
    
    # 获取用户信息
    cursor.execute("SELECT user_id, username, followers_count, friends_count, tweets_count FROM users WHERE username = ?", (username,))
    user_row = cursor.fetchone()
    
    if not user_row:
        conn.close()
        return [], []
    
    user_id, username_db, followers_count, friends_count, tweets_count = user_row
    
    # 获取推文
    cursor.execute("""
        SELECT tweet_id, created_at, author_id, full_text, 
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
        # 确保 full_text 是字符串类型
        full_text = str(row[3]) if row[3] is not None else ""
        
        tweet = Tweet(
            tweet_id=str(row[0]) if row[0] is not None else "",
            author_id=str(row[2]) if row[2] is not None else "",
            full_text=full_text,
            likes_count=int(row[4]) if row[4] is not None else 0,
            retweets_count=int(row[5]) if row[5] is not None else 0,
            replies_count=int(row[6]) if row[6] is not None else 0,
            views_count=int(row[7]) if row[7] is not None else 0,
            in_reply_to_status_id_str=str(row[8]) if len(row) > 8 and row[8] is not None else None,
            is_quote_status=int(row[9]) if len(row) > 9 and row[9] is not None else 0
        )
        all_tweets.append(tweet)
    
    # 限制推文数量（防止 AI 调用过多）
    tweets_for_scoring = all_tweets[:TWEETS_LIMIT] if len(all_tweets) > TWEETS_LIMIT else all_tweets
    
    # 创建 Account 对象
    account = Account(
        user_id=user_id,
        username=username_db,
        description="",
        followers_count=followers_count or 0,
        friends_count=friends_count or 0,
        tweets_count=tweets_count or 0,
        tweets=tweets_for_scoring
    )
    
    return [account], all_tweets


def process_user(username: str, task_id: str):
    """处理用户分析任务（在后台线程中运行）"""
    try:
        tasks[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '开始处理...',
            'error': None,
            'result': None
        }
        
        # 检查 API 密钥
        TWEETSCOUT_API_KEY = os.getenv("TWEETSCOUT_API_KEY")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        if not TWEETSCOUT_API_KEY:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = '未设置 TWEETSCOUT_API_KEY 环境变量'
            return
        
        if not OPENAI_API_KEY:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = '未设置 OPENAI_API_KEY 环境变量'
            return
        
        # 确保目录存在
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(STATIC_HTML_DIR, exist_ok=True)
        
        twitter_db_path = os.path.join(DATA_DIR, f"twitter_data_{username}.db")
        
        # 步骤 1: 爬取数据
        tasks[task_id]['progress'] = 10
        tasks[task_id]['message'] = 'Crawling data...'
        
        crawler = TwitterCrawler(
            api_key=TWEETSCOUT_API_KEY,
            output_dir=DATA_DIR,
            db_name=f"twitter_data_{username}.db"
        )
        
        try:
            result = crawler.crawl_user(
                username=username,
                max_tweets=MAX_TWEETS,
                skip_comments=SKIP_COMMENTS
            )
            
            if not result or result.get('tweets_crawled', 0) == 0:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['error'] = f'未能爬取到 {username} 的推文数据'
                return
            
        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = f'爬取失败: {str(e)}'
            return
        finally:
            crawler.close()
        
        # 步骤 2: 转换数据格式
        tasks[task_id]['progress'] = 30
        tasks[task_id]['message'] = 'Converting data format...'
        
        try:
            accounts, all_tweets = convert_twitter_db_to_scoring_format(twitter_db_path, username)
            
            if not accounts or len(accounts) == 0:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['error'] = f'No user data found: {username}'
                return
            
            account = accounts[0]
            
            if len(account.tweets) == 0:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['error'] = 'This user has no tweet data, cannot calculate score'
                return
            
        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = f'Data conversion failed: {str(e)}'
            return
        
        # 步骤 3: 计算评分
        tasks[task_id]['progress'] = 50
        tasks[task_id]['message'] = 'Calculating score (this may take some time)...'
        
        norm_manager = NormalizationManager()
        norm_manager.load_normalization_params()
        
        try:
            result = asyncio.run(calculate(accounts, score_tree, 
                                          normalization_manager=norm_manager,
                                          save_history=True))
            
            # 保存数据
            with open(os.path.join(OUTPUT_DIR, f"accounts_{username}.json"), "w", encoding="utf-8") as f:
                json.dump([asdict(account) for account in accounts], f, ensure_ascii=False, indent=2)
            
            with open(os.path.join(OUTPUT_DIR, f"tweets_{username}.json"), "w", encoding="utf-8") as f:
                json.dump([asdict(tweet) for tweet in all_tweets], f, ensure_ascii=False, indent=2)
            
            with open(os.path.join(OUTPUT_DIR, f"scores_{username}.json"), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            save_tree_structure(score_tree, os.path.join(OUTPUT_DIR, f"tree_structure_{username}.json"))
            
        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = f'Score calculation failed: {str(e)}'
            return
        
        # 步骤 4: 生成 HTML 网页
        tasks[task_id]['progress'] = 80
        tasks[task_id]['message'] = 'Generating evaluation page...'
        
        try:
            # 读取数据
            accounts_data = read_json_file(os.path.join(OUTPUT_DIR, f"accounts_{username}.json"))
            scores_data = read_json_file(os.path.join(OUTPUT_DIR, f"scores_{username}.json"))
            tree_structure = read_json_file(os.path.join(OUTPUT_DIR, f"tree_structure_{username}.json"))
            
            scores = scores_data.get('scores', scores_data)
            comments = scores_data.get('comments', {})
            
            # 生成主页面
            main_html = generate_main_page(accounts_data, scores, tree_structure)
            main_file = os.path.join(STATIC_HTML_DIR, f'index_{username}.html')
            with open(main_file, 'w', encoding='utf-8') as f:
                f.write(main_html)
            
            # 生成用户详细页面
            user_html = generate_user_page(accounts_data[0], scores, comments, tree_structure, 0)
            user_file = os.path.join(STATIC_HTML_DIR, f'user_{username}.html')
            with open(user_file, 'w', encoding='utf-8') as f:
                f.write(user_html)
            
            # 完成
            tasks[task_id]['progress'] = 100
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['message'] = 'Completed!'
            tasks[task_id]['result'] = {
                'username': username,
                'main_page': f'/static_html/index_{username}.html',
                'user_page': f'/static_html/user_{username}.html',
                'root_score': scores.get('root', [0])[0] if scores.get('root') else 0
            }
            
        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = f'Failed to generate page: {str(e)}'
            return
            
    except Exception as e:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['error'] = f'Processing failed: {str(e)}'


@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """分析用户API"""
    data = request.json
    username = data.get('username', '').strip().lstrip('@')
    
    if not username:
        return jsonify({'error': 'Please enter a username'}), 400
    
    # 生成任务ID
    import uuid
    task_id = str(uuid.uuid4())
    
    # 启动后台任务
    thread = threading.Thread(target=process_user, args=(username, task_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'message': 'Task started'
    })


@app.route('/api/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify(tasks[task_id])


@app.route('/static_html/<path:filename>')
def serve_static_html(filename):
    """提供静态HTML文件"""
    return send_from_directory(STATIC_HTML_DIR, filename)


@app.route('/api/history', methods=['GET'])
def get_history():
    """获取历史查询记录"""
    try:
        history_file = os.path.join(OUTPUT_DIR, "raw_scores_history.json")
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            # 提取用户名列表，并检查对应的HTML文件是否存在
            history_list = []
            for username in history_data.keys():
                user_page = os.path.join(STATIC_HTML_DIR, f'user_{username}.html')
                main_page = os.path.join(STATIC_HTML_DIR, f'index_{username}.html')
                
                # 检查文件是否存在
                has_user_page = os.path.exists(user_page)
                has_main_page = os.path.exists(main_page)
                
                if has_user_page or has_main_page:
                    history_list.append({
                        'username': username,
                        'has_user_page': has_user_page,
                        'has_main_page': has_main_page,
                        'user_page_url': f'/static_html/user_{username}.html' if has_user_page else None,
                        'main_page_url': f'/static_html/index_{username}.html' if has_main_page else None
                    })
            
            # 按用户名排序
            history_list.sort(key=lambda x: x['username'].lower())
            
            return jsonify({
                'success': True,
                'history': history_list
            })
        else:
            return jsonify({
                'success': True,
                'history': []
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("KOL Evaluation Report Generator - Web Service")
    print("=" * 60)
    print("Visit http://localhost:5000 to use the web interface")
    print()
    app.run(debug=True, host='0.0.0.0', port=5000)

