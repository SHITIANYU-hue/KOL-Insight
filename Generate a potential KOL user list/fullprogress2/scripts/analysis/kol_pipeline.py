#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse
import os
import sqlite3
import logging
import concurrent.futures
from datetime import datetime
from typing import List, Dict

import pandas as pd
from tqdm import tqdm
from openai import OpenAI

MODEL_NAME = "o3-mini"
client = OpenAI(api_key="你的openai api")  # API key 从环境变量 OPENAI_API_KEY 读取

# ----------------------------------------------------------------------------
# SQL helpers
# ----------------------------------------------------------------------------

def ensure_kol_table(cur: sqlite3.Cursor):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS kol_status (
        author_id TEXT PRIMARY KEY,
        kol_status TEXT CHECK(kol_status IN ('yes','no','maybe')),
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.connection.commit()

def upsert_kol(cur: sqlite3.Cursor, author_id: str, status: str):
    cur.execute(
        """INSERT INTO kol_status(author_id, kol_status, checked_at)
           VALUES(?,?,?)
           ON CONFLICT(author_id) DO UPDATE SET
               kol_status=excluded.kol_status,
               checked_at=excluded.checked_at""",
        (author_id, status, datetime.utcnow()),
    )
    cur.connection.commit()

# ----------------------------------------------------------------------------
# GPT prompt & call
# ----------------------------------------------------------------------------

def build_prompt(user: Dict, recent: List[str]) -> str:
    prompt = (
        f"严格分析此Twitter/X用户是否是真正的加密货币/Web3 KOL（关键意见领袖）:\n"
        f"名称: {user['name']} (@{user['screen_name']})\n"
        f"简介: {user['description']}\n"
    )
    if recent:
        prompt += "最近推文:\n"
        for i, tw in enumerate(recent[:3], 1):
            snippet = (tw[:200] + "…") if len(tw) > 200 else tw
            prompt += f"{i}. {snippet}\n"
    prompt += (
        '\n判断标准：\n'
        '1. 经常发布有深度的加密货币/Web3内容\n'
        '2. 平台创始人、投资者或项目方如有优质内容也可视为KOL\n'
        '3. 有一定关注者和影响力\n'
        '4. 内容有一定教育、分析或见解价值，不是纯营销\n\n'
        '请直接回答"YES"如果符合大部分标准，"NO"如果完全不符合，"MAYBE"如果不确定，'
        '并附简短理由（不超过30字）。'
    )
    return prompt

def ask_gpt(prompt: str) -> str:
    try:
        rsp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是严格的Web3社交媒体分析专家，只认定真正持续输出优质Web3内容的账户为KOL。"},
                {"role": "user", "content": prompt},
            ],
            timeout=60,
        )
        text = rsp.choices[0].message.content.upper()
        if "YES" in text:
            return "yes"
        if "NO" in text:
            return "no"
        return "maybe"
    except Exception as e:
        logging.warning("GPT 调用出错，标记为 maybe: %s", e)
        return "maybe"

# ----------------------------------------------------------------------------
# Single-user processing (for ThreadPool)
# ----------------------------------------------------------------------------

def _process_one(user: Dict, tweets_df: pd.DataFrame, max_tweets: int) -> tuple[str,str]:
    recent = tweets_df.loc[tweets_df["author_id"] == user["user_id"], "full_text"].head(max_tweets).tolist()
    prompt = build_prompt(user, recent)
    status = ask_gpt(prompt)
    return user["user_id"], status

# ----------------------------------------------------------------------------
# Export yes/no DBs
# ----------------------------------------------------------------------------

def _export_kol_dbs(ana_conn: sqlite3.Connection, fol_conn: sqlite3.Connection, db_dir: str):
    yes_ids = [r[0] for r in ana_conn.execute("SELECT author_id FROM kol_status WHERE kol_status='yes'")]
    no_ids  = [r[0] for r in ana_conn.execute("SELECT author_id FROM kol_status WHERE kol_status='no'")]

    for ids, fname in ((yes_ids, "KOL_yes.db"), (no_ids, "KOL_no.db")):
        path = os.path.join(db_dir, fname)
        if os.path.exists(path):
            os.remove(path)
        conn_out = sqlite3.connect(path)
        cur_out  = conn_out.cursor()

        fol_path = os.path.join(db_dir, "followingA.db")
        cur_out.execute(f"ATTACH DATABASE '{fol_path}' AS fol")

        try:
            # 创建空 users 表
            cur_out.execute("CREATE TABLE users AS SELECT * FROM fol.users WHERE 0")

            # 插入对应记录
            if ids:
                placeholders = ",".join("?" for _ in ids)
                cur_out.execute(
                    f"INSERT INTO users SELECT * FROM fol.users WHERE user_id IN ({placeholders})",
                    ids
                )
            conn_out.commit()  # 确保所有写操作已提交
            cur_out.close()    # 关闭游标，释放锁
            # 用新游标专门用于 DETACH
            cur_detach = conn_out.cursor()
            cur_detach.execute("DETACH DATABASE fol")
            cur_detach.close()
            conn_out.commit()
        finally:
            conn_out.close()
        logging.info("导出 %s，记录数=%d", fname, len(ids))

# ----------------------------------------------------------------------------
# Main流程
# ----------------------------------------------------------------------------

def main(db_dir: str, target_kols: int, max_tweets: int, batch_size: int = 50):
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
    ana_path = os.path.join(db_dir, "analytics.db")
    fol_path = os.path.join(db_dir, "followingA.db")
    tw_path  = os.path.join(db_dir, "tweets.db")

    # 打开数据库连接
    ana_conn = sqlite3.connect(ana_path)
    ana_cur  = ana_conn.cursor()
    fol_conn = sqlite3.connect(fol_path)
    tw_conn  = sqlite3.connect(tw_path)

    # 确保 kol_status 表存在
    ensure_kol_table(ana_cur)

    # 1) 如果已有足够的 YES，直接导出
    ana_cur.execute("SELECT COUNT(*) FROM kol_status WHERE kol_status='yes'")
    yes_count = ana_cur.fetchone()[0]
    logging.info("已有 YES 数: %d / %d", yes_count, target_kols)
    if yes_count >= target_kols:
        logging.info("已满足目标，直接导出数据库")
        _export_kol_dbs(ana_conn, fol_conn, db_dir)
        return

    # 2) 从 analytics 拿所有候选 author_id
    cand_df = pd.read_sql("SELECT author_id FROM user_originality_enhanced", ana_conn)
    all_ids = cand_df["author_id"].astype(str).tolist()

    # 3) 排除已经确认 YES 的，只对 NO/MAYBE 或未评定的继续
    ana_cur.execute("SELECT author_id FROM kol_status WHERE kol_status='yes'")
    done_yes = {r[0] for r in ana_cur.fetchall()}
    pending  = [uid for uid in all_ids if uid not in done_yes]
    logging.info("待评定候选总数: %d", len(pending))
    if not pending:
        logging.warning("无待评定用户，导出并退出")
        _export_kol_dbs(ana_conn, fol_conn, db_dir)
        return

    # # 4) 只取剩余所需的两倍量（防 maybe/no 太多）
    # need       = target_kols - yes_count
    # to_process = pending[: need * 5]

    # 4) 取出followingA.db里所有的
    need       = target_kols - yes_count
    to_process = pending
    logging.info("本次规划处理: %d 位 (need=%d)", len(to_process), need)

    # 5) 读取用户简介
    placeholders = ",".join("?" for _ in to_process)
    info_df = pd.read_sql(
        f"SELECT user_id, username AS name, screen_name, description FROM users "
        f"WHERE user_id IN ({placeholders})",
        fol_conn,
        params=to_process
    )

    # 6) 读取推文内容
    tweets_list: List[pd.DataFrame] = []
    for uid in tqdm(to_process, desc="加载推文"):
        df = pd.read_sql(
            "SELECT author_id, full_text FROM tweets "
            "WHERE author_id=? ORDER BY created_at DESC LIMIT ?",
            tw_conn, params=[uid, max_tweets]
        )
        tweets_list.append(df)
    tweets_df = pd.concat(tweets_list, ignore_index=True) if tweets_list else pd.DataFrame(columns=["author_id","full_text"])

    # 7) 分批并发调用 GPT 评定
    kol_yes = yes_count
    total   = len(to_process)
    batches = (total + batch_size - 1) // batch_size

    for i in range(batches):
        batch_ids   = to_process[i*batch_size : (i+1)*batch_size]
        batch_users = info_df[info_df["user_id"].isin(batch_ids)].to_dict("records")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = { pool.submit(_process_one, u, tweets_df, max_tweets): u for u in batch_users }
            for fut in tqdm(concurrent.futures.as_completed(futures),
                            total=len(batch_users),
                            desc=f"评定批次 {i+1}/{batches}"):
                uid, status = fut.result()
                upsert_kol(ana_cur, uid, status)
                if status == "yes":
                    kol_yes += 1
                    logging.info("新增 YES: %s (total=%d)", uid, kol_yes)
                if kol_yes >= target_kols:
                    logging.info("达到目标 YES 数 %d，提前退出评定", target_kols)
                    break

        if kol_yes >= target_kols:
            break

    # 8) 导出最终的 KOL_yes.db 和 KOL_no.db
    _export_kol_dbs(ana_conn, fol_conn, db_dir)

    # 9) 关闭所有连接
    ana_conn.close()
    fol_conn.close()
    tw_conn.close()
    logging.info("kol_pipeline 完成！")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db_dir",     type=str, default=".", help="数据库所在目录")
    parser.add_argument("--target_kols",type=int, required=True, help="所需的 KOL 数量")
    parser.add_argument("--max_tweets", type=int, default=20, help="每人抓取推文数")
    parser.add_argument("--batch_size", type=int, default=50, help="每批次评定数量")
    args = parser.parse_args()

    main(args.db_dir, args.target_kols, args.max_tweets, args.batch_size)
