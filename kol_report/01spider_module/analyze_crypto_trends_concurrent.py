#!/usr/bin/env python3
# process_crypto_tweets.py  —  处理推文中的加密货币推荐
# 依赖：python ≥3.9,  openai>=1.14.0

import os
import json
import sqlite3
import asyncio
import logging
import time
import argparse
import re
from datetime import datetime
from typing import List, Dict, Optional

from openai import AsyncOpenAI          # pip install --upgrade openai>=1.14.0

# ────────────────────────── 全局配置 ────────────────────────── #
SEARCH_MODEL   = "gpt-4o-search-preview"   # 查 CoinGecko id
ANALYSIS_MODEL = "o3-mini"                      # 判定 long/short term
MAX_CONCURRENT = 20                             # 默认并发
# ───────────────────────────────────────────────────────────── #

class CryptoProcessor:
    def __init__(self, db_dir: str, api_key: str, max_concurrent: int = MAX_CONCURRENT):
        self.db_dir         = db_dir
        self.tweets_db_path = os.path.join(db_dir, "tweets.db")
        self.trade_db_path  = os.path.join(db_dir, "guid_to_trade_tweet.db")
        self.output_db_path = os.path.join(db_dir, "crypto_recommendations.db")
        self.max_concurrent = max_concurrent

        # OpenAI 异步客户端
        self.search_client   = AsyncOpenAI(api_key=api_key)
        self.analysis_client = AsyncOpenAI(api_key=api_key)

        self._setup_logging()
        self._init_database()

        self.db_lock       = asyncio.Lock()
        self.api_call_cnt  = 0
        self.start_time    = 0.0

    # ─────────────── 日志 & DB ─────────────── #
    def _setup_logging(self):
        os.makedirs(os.path.join(self.db_dir, "logs"), exist_ok=True)
        log_path = os.path.join(
            self.db_dir, "logs",
            f"crypto_processor_{datetime.now():%Y%m%d_%H%M%S}.log"
        )
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s",
            handlers=[logging.FileHandler(log_path),
                      logging.StreamHandler()],
        )
        self.logger = logging.getLogger("CryptoProcessor")

    def _init_database(self):
        os.makedirs(self.db_dir, exist_ok=True)
        if os.path.exists(self.output_db_path):
            bak = f"{self.output_db_path}.{int(time.time())}.bak"
            os.rename(self.output_db_path, bak)
            self.logger.info("已备份旧输出数据库 → %s", bak)

        self.out_conn   = sqlite3.connect(self.output_db_path, check_same_thread=False)
        self.out_cursor = self.out_conn.cursor()
        self.out_cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS crypto_recommendations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tweet_id TEXT NOT NULL,
              author_id TEXT,
              author_name TEXT,
              tweet_created_at TEXT,
              investment_horizon TEXT NOT NULL,
              crypto_name TEXT NOT NULL,
              coingecko_id TEXT,
              full_tweet_text TEXT,
              processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(tweet_id, crypto_name)
            )
            """
        )
        for col in ("tweet_id","investment_horizon","crypto_name","coingecko_id"):
            self.out_cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{col} ON crypto_recommendations({col})"
            )
        self.out_conn.commit()
        self.logger.info("输出数据库初始化完成 → %s", self.output_db_path)

    # ─────────────── 数据加载 ─────────────── #
    def _load_trade_tweets(self) -> List[Dict]:
        if not os.path.exists(self.trade_db_path):
            self.logger.error("交易推文数据库不存在: %s", self.trade_db_path)
            return []
        conn = sqlite3.connect(self.trade_db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT guid, tweet_id, author_id, author_name,
                   full_text, created_at, buy_what, advice_content
              FROM trade_tweets
             WHERE has_trade_advice = 1
             ORDER BY created_at DESC
            """
        ).fetchall()
        conn.close()
        self.logger.info("加载交易推文 %d 条", len(rows))
        return [dict(r) for r in rows]

    def _get_tweet_date(self, tweet_id:str) -> Optional[str]:
        if not os.path.exists(self.tweets_db_path):
            return None
        conn = sqlite3.connect(self.tweets_db_path)
        row  = conn.execute("SELECT created_at FROM tweets WHERE tweet_id=?",(tweet_id,)).fetchone()
        conn.close()
        if not row or not row[0]:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S.%fZ"):
            try:
                return datetime.strptime(str(row[0]), fmt).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return None

    # ─────────────── 文本工具 ─────────────── #
    @staticmethod
    def _split_crypto_names(names: str) -> List[str]:
        if not names:
            return []
        norm = re.sub(r"\s+and\s+|\s*&\s*|\s*,\s*|\s+、\s+|\s+和\s+|\s+or\s+", "|", names)
        uniq, seen = [], set()
        for tok in norm.split("|"):
            tok = tok.strip()
            if tok and tok not in seen:
                uniq.append(tok); seen.add(tok)
        return uniq

    # ─────────────── OpenAI 调用 ─────────────── #
    async def _analyze_horizon(self, full_text:str, advice:str) -> str:
        self.api_call_cnt += 1
        prompt = (
            "Analyze the following crypto tweet and return ONLY one word: "
            '"short_term" or "long_term".\n\n'
            f'Tweet: "{full_text}"\n'
            f'Advice: "{advice}"\n\n'
            'Respond with ONLY one word (lowercase, underscore).'
        )
        try:
            rsp = await self.analysis_client.chat.completions.create(
                model=ANALYSIS_MODEL,
                messages=[{"role":"user","content":prompt}],
            )
            word = rsp.choices[0].message.content.strip().lower()
            return word if word in {"short_term","long_term"} else "short_term"
        except Exception as e:
            self.logger.error("分析投资期限失败: %s", e)
            return "short_term"

    async def _get_coingecko_id(self, name:str) -> str:
        self.api_call_cnt += 1
        messages = [
            {
                "role":"system",
                "content":"Return ONLY the CoinGecko id (lowercase, hyphen). "
                          "If not found, return NOT_FOUND. No other text."
            },
            {
                "role":"user",
                "content":f"Find CoinGecko id for {name}"
            },
        ]
        try:
            rsp = await self.search_client.chat.completions.create(
                model=SEARCH_MODEL,
                web_search_options={"search_context_size":"high"},
                messages=messages,
            )
            raw = rsp.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error("API 错误: %s", e)
            raw = ""

        first = raw.splitlines()[0] if raw else ""
        cid   = first.strip().strip('"`').lower()
        if not re.fullmatch(r"[a-z0-9\-]{3,}", cid):
            cid = "NOT_FOUND"
        return cid

    # ─────────────── DB 写入 ─────────────── #
    async def _save(self, tw:Dict, name:str, cid:str, horizon:str):
        date_str = self._get_tweet_date(tw["tweet_id"])
        async with self.db_lock:
            self.out_cursor.execute(
                """
                INSERT OR REPLACE INTO crypto_recommendations
                (tweet_id, author_id, author_name, tweet_created_at,
                 investment_horizon, crypto_name, coingecko_id, full_tweet_text)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    tw["tweet_id"],
                    tw.get("author_id"),
                    tw.get("author_name"),
                    date_str,
                    horizon,
                    name,
                    cid,
                    tw.get("full_text","")
                ),
            )
            self.out_conn.commit()

    # ─────────────── 处理单推文 ─────────────── #
    async def _process_tweet(self, tw:Dict, sem:asyncio.Semaphore):
        async with sem:
            names = self._split_crypto_names(tw.get("buy_what",""))
            if not names:
                self.logger.warning("跳过无币种推文 %s", tw.get("tweet_id"))
                return

            horizon = await self._analyze_horizon(
                tw.get("full_text",""), tw.get("advice_content","")
            )
            self.logger.info("推文 %s horizon=%s names=%s",
                             tw.get("tweet_id"), horizon, names)

            ids = await asyncio.gather(*[self._get_coingecko_id(n) for n in names])
            for n,cid in zip(names, ids):
                await self._save(tw, n, cid, horizon)

    # ─────────────── 主流程 ─────────────── #
    async def run_async(self):
        self.start_time = time.time()
        tweets = self._load_trade_tweets()
        if not tweets:
            self.logger.warning("无推文可处理"); return

        sem   = asyncio.Semaphore(self.max_concurrent)
        tasks = [asyncio.create_task(self._process_tweet(tw, sem)) for tw in tweets]

        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 10 == 0:
                elapsed = time.time() - self.start_time
                rate = self.api_call_cnt / elapsed if elapsed else 0
                self.logger.info("进度 %d/%d | API %.1f 次/秒",
                                 done, len(tasks), rate)

        # 统计输出
        self.logger.info("\n=== 投资期限统计 ===")
        for row in self.out_cursor.execute(
            """
            SELECT investment_horizon,
                   COUNT(DISTINCT crypto_name) AS uniq,
                   COUNT(*) AS cnt
              FROM crypto_recommendations
             GROUP BY investment_horizon
            """
        ):
            self.logger.info("%s: %d 种币, %d 条", row[0], row[1], row[2])

        self.logger.info("\n=== 热门币种 TOP10 ===")
        for r in self.out_cursor.execute(
            """
            SELECT crypto_name, coingecko_id, COUNT(*) cnt
              FROM crypto_recommendations
             WHERE coingecko_id NOT IN ('ERROR','NOT_FOUND')
          GROUP BY crypto_name
          ORDER BY cnt DESC
             LIMIT 10
            """
        ):
            self.logger.info("%-15s (%s)  %d 次", r[0], r[1], r[2])

        self.out_conn.close()
        self.logger.info("总耗时 %.2fs | API 调用 %d",
                         time.time()-self.start_time, self.api_call_cnt)

    # 同步入口
    def run(self):
        asyncio.run(self.run_async())

# ─────────────── CLI ─────────────── #
def main():
    ap = argparse.ArgumentParser(description="处理包含加密交易建议的推文")
    ap.add_argument("--db_dir", default=".", help="数据库文件夹 (含 tweets.db 等)")
    ap.add_argument("--api_key", required=True, help="OpenAI API Key")
    ap.add_argument("--max_concurrent", type=int, default=MAX_CONCURRENT,
                    help=f"最大并发 (默认 {MAX_CONCURRENT})")
    args = ap.parse_args()

    CryptoProcessor(args.db_dir, args.api_key, args.max_concurrent).run()

if __name__ == "__main__":
    main()
