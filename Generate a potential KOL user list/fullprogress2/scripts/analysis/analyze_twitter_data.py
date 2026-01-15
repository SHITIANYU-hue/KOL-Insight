#!/usr/bin/env python3
"""Merged analytics script

生成两张表:
  • enhanced_tweets
  • user_originality_enhanced
存储在 analytics.db

用法:
    python3 analyze_twitter_data.py --db_dir /path/to/dir
"""
import os
import sqlite3
import argparse
import logging
from typing import Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def attach_db(cur: sqlite3.Cursor, alias: str, path: str) -> None:
    cur.execute(f"ATTACH DATABASE '{path}' AS {alias}")

# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def run_analysis(db_dir: str = ".") -> Tuple[str, str]:
    """Compute metrics and write to analytics.db.

    Returns
    -------
    Tuple[path to analytics.db, log message]
    """
    tweets_path     = os.path.join(db_dir, "tweets.db")
    following_path  = os.path.join(db_dir, "followingA.db")
    analytics_path  = os.path.join(db_dir, "analytics.db")

    if not os.path.exists(tweets_path):
        raise FileNotFoundError(f"未找到 tweets.db: {tweets_path}")
    if not os.path.exists(following_path):
        raise FileNotFoundError(f"未找到 followingA.db: {following_path}")

    log = logging.getLogger("analyse")
    log.info("打开 tweets.db …")
    tw_conn = sqlite3.connect(tweets_path)
    tw_cur  = tw_conn.cursor()

    # 将 followingA.db 附加为 fa
    attach_db(tw_cur, "fa", following_path)

    log.info("准备输出库 analytics.db …")
    out_conn = sqlite3.connect(analytics_path)
    out_cur  = out_conn.cursor()

    # ------------------ 建表 -------------------
    out_cur.executescript(
        """
        PRAGMA foreign_keys = OFF;
        CREATE TABLE IF NOT EXISTS enhanced_tweets (
            tweet_id TEXT PRIMARY KEY,
            author_id TEXT,
            author_name TEXT,
            likes_count INTEGER,
            retweets_count INTEGER,
            replies_count INTEGER,
            quote_count INTEGER,
            views_count INTEGER,
            author_followers_count INTEGER,
            author_friends_count INTEGER,
            total_interactions INTEGER,
            engagement_rate REAL,
            views_per_follower REAL,
            like_ratio REAL,
            retweet_ratio REAL,
            reply_ratio REAL,
            quote_ratio REAL
        );

        CREATE TABLE IF NOT EXISTS user_originality_enhanced (
            author_id TEXT PRIMARY KEY,
            author_name TEXT,
            total_count INTEGER,
            original_count INTEGER,
            original_ratio REAL,
            tweet_count INTEGER,
            author_followers_count INTEGER,
            author_friends_count INTEGER,
            views_count INTEGER,
            total_interactions INTEGER,
            overall_engagement_rate REAL,
            avg_interactions_per_tweet REAL,
            avg_views_per_tweet REAL,
            engagement_rate REAL,
            views_per_follower REAL,
            overall_like_ratio REAL,
            overall_retweet_ratio REAL,
            overall_reply_ratio REAL,
            overall_quote_ratio REAL
        );
        """
    )

    # ------------------ 1. 用户原创性 -------------------
    log.info("计算原创性…")
    df_orig = pd.read_sql(
        """
        SELECT author_id,
               MAX(author_name) AS author_name,
               COUNT(*)                                            AS total_count,
               SUM(CASE WHEN full_text LIKE 'RT @%' THEN 0 ELSE 1 END) AS original_count,
               AVG(CASE WHEN full_text LIKE 'RT @%' THEN 0 ELSE 1 END) AS original_ratio
        FROM tweets
        GROUP BY author_id
        """,
        tw_conn,
    )

    # ------------------ 2. 原创推文及指标 -------------------
    log.info("提取原创推文…")
    df_tw = pd.read_sql(
        """
        SELECT t.tweet_id,
               t.author_id,
               t.author_name,
               t.likes_count,
               t.retweets_count,
               t.replies_count,
               0                   AS quote_count,
               t.views_count,
               fa.users.followers_count AS author_followers_count,
               fa.users.friends_count   AS author_friends_count
        FROM tweets t
        JOIN fa.users ON fa.users.user_id = t.author_id
        WHERE t.full_text NOT LIKE 'RT @%'
        """,
        tw_conn,
    )

    log.info("计算推文级互动指标…")
    df_tw["total_interactions"] = (
        df_tw["likes_count"] + df_tw["retweets_count"] +
        df_tw["replies_count"] + df_tw["quote_count"]
    )
    df_tw["engagement_rate"] = np.where(
        df_tw["views_count"] > 0,
        df_tw["total_interactions"] / df_tw["views_count"], 0,
    )
    df_tw["views_per_follower"] = np.where(
        df_tw["author_followers_count"] > 0,
        df_tw["views_count"] / df_tw["author_followers_count"], 0,
    )
    for col, new in [
        ("likes_count", "like_ratio"),
        ("retweets_count", "retweet_ratio"),
        ("replies_count", "reply_ratio"),
        ("quote_count", "quote_ratio"),
    ]:
        df_tw[new] = np.where(
            df_tw["total_interactions"] > 0,
            df_tw[col] / df_tw["total_interactions"], 0,
        )

    # 写入 enhanced_tweets (UPSERT)
    log.info("写入 enhanced_tweets…")
    df_tw.to_sql(
        "enhanced_tweets",
        out_conn,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=500,
    )

    # ------------------ 3. 用户级聚合 -------------------
    log.info("计算用户级指标…")
    agg = {
        "likes_count": "sum",
        "retweets_count": "sum",
        "replies_count": "sum",
        "quote_count": "sum",
        "views_count": "sum",
        "total_interactions": "sum",
        "engagement_rate": "mean",
        "views_per_follower": "mean",
        "author_followers_count": "first",
        "author_friends_count": "first",
        "author_name": "first",  # 保留第一个用户名
    }
    
    # 主要指标只按 author_id 分组计算
    agg_metrics = df_tw.groupby("author_id").agg(agg).reset_index()
    
    # 计算推文数量
    agg_metrics["tweet_count"] = df_tw.groupby("author_id").size().values  # 现在长度匹配了
    
    agg_metrics["overall_engagement_rate"] = np.where(
        agg_metrics["views_count"] > 0,
        agg_metrics["total_interactions"] / agg_metrics["views_count"], 0,
    )
    for col, new in [
        ("likes_count", "overall_like_ratio"),
        ("retweets_count", "overall_retweet_ratio"),
        ("replies_count", "overall_reply_ratio"),
        ("quote_count", "overall_quote_ratio"),
    ]:
        agg_metrics[new] = np.where(
            agg_metrics["total_interactions"] > 0,
            agg_metrics[col] / agg_metrics["total_interactions"], 0,
        )
    agg_metrics["avg_interactions_per_tweet"] = agg_metrics["total_interactions"] / agg_metrics["tweet_count"]
    agg_metrics["avg_views_per_tweet"]       = agg_metrics["views_count"] / agg_metrics["tweet_count"]

    # ------------------ 4. 合并原创性 -------------------
    df_final = df_orig.merge(agg_metrics, on="author_id", how="left")

    log.info("写入 user_originality_enhanced…")
    df_final.to_sql(
        "user_originality_enhanced",
        out_conn,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=200,
    )

    out_conn.commit()
    tw_conn.close(); out_conn.close()
    log.info("分析完成，结果写入 %s", analytics_path)
    return analytics_path, "success"

# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--db_dir", type=str, default=".", help="tweets.db 与 followingA.db 所在目录")
    args = parser.parse_args()
    run_analysis(args.db_dir)
