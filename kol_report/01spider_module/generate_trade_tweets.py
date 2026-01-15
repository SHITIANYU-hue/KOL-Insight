#!/usr/bin/env python3
# generate_trade_tweets_fixed.py - 修复版本，解决JSON解析和分类问题
# 输入：tweets.db，输出：guid_to_trade_tweet.db

import os
import json
import sqlite3
import asyncio
import logging
import time
import argparse
import re
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Set

from openai import AsyncOpenAI

# ────────────────────────── 全局配置 ────────────────────────── #
SEARCH_MODEL = "gpt-4o-search-preview"   # 查找 CoinGecko ID
CLASSIFICATION_MODEL = "gpt-4o"          # 分类交易建议
MAX_CONCURRENT = 5                       # 降低并发数避免API限制
# ───────────────────────────────────────────────────────────── #

class TradeTweetGenerator:
    def __init__(self, db_dir: str, api_key: str, max_concurrent: int = MAX_CONCURRENT, blacklist_path: Optional[str] = None):
        self.db_dir = db_dir
        self.tweets_db_path = os.path.join(db_dir, "tweets.db")
        self.output_db_path = os.path.join(db_dir, "guid_to_trade_tweet.db")
        self.max_concurrent = max_concurrent

        # OpenAI 异步客户端
        self.search_client = AsyncOpenAI(api_key=api_key)
        self.classification_client = AsyncOpenAI(api_key=api_key)

        self._setup_logging()
        self._init_database()
        # 加载黑名单（如果提供或存在默认文件）
        self.blacklist = self._load_blacklist(blacklist_path)

        self.db_lock = asyncio.Lock()
        self.api_call_cnt = 0
        self.start_time = 0.0

    def _setup_logging(self):
        os.makedirs(os.path.join(self.db_dir, "logs"), exist_ok=True)
        log_path = os.path.join(
            self.db_dir, "logs",
            f"trade_tweet_generator_fixed_{datetime.now():%Y%m%d_%H%M%S}.log"
        )
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s",
            handlers=[logging.FileHandler(log_path),
                      logging.StreamHandler()],
        )
        self.logger = logging.getLogger("TradeTweetGenerator")

    def _init_database(self):
        os.makedirs(self.db_dir, exist_ok=True)
        if os.path.exists(self.output_db_path):
            bak = f"{self.output_db_path}.{int(time.time())}.bak"
            os.rename(self.output_db_path, bak)
            self.logger.info("已备份旧输出数据库 → %s", bak)

        self.out_conn = sqlite3.connect(self.output_db_path, check_same_thread=False)
        self.out_cursor = self.out_conn.cursor()
        # 创建与analyze_crypto_trends_concurrent.py完全匹配的表结构
        self.out_cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_tweets (
              guid TEXT PRIMARY KEY,
              tweet_id TEXT NOT NULL,
              author_id TEXT,
              author_name TEXT,
              full_text TEXT,
              created_at TEXT,
              buy_what TEXT,
              advice_content TEXT,
              has_trade_advice INTEGER DEFAULT 0,
              processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # 创建索引
        for col in ("tweet_id", "author_id", "has_trade_advice"):
            self.out_cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{col} ON trade_tweets({col})"
            )
        self.out_conn.commit()
        self.logger.info("输出数据库初始化完成 → %s", self.output_db_path)

    def _load_tweets(self) -> List[Dict]:
        """从 tweets.db 加载所有推文"""
        if not os.path.exists(self.tweets_db_path):
            self.logger.error("推文数据库不存在: %s", self.tweets_db_path)
            return []
        
        conn = sqlite3.connect(self.tweets_db_path)
        conn.row_factory = sqlite3.Row
        # 读取用于判断是否为非原创的字段（reply/quote/retweeted）
        rows = conn.execute(
            """
            SELECT tweet_id, author_id, author_name, full_text, created_at,
                   in_reply_to_status_id_str, is_quote_status, quoted_status, retweeted_status
            FROM tweets
            WHERE full_text IS NOT NULL AND full_text != ''
            ORDER BY created_at DESC
            """
        ).fetchall()
        conn.close()

        # 过滤非原创推文：满足任一条件即为非原创
        originals = []
        for r in rows:
            in_reply = r.get('in_reply_to_status_id_str') if isinstance(r, dict) else r['in_reply_to_status_id_str']
            is_quote = r.get('is_quote_status') if isinstance(r, dict) else r['is_quote_status']
            quoted = r.get('quoted_status') if isinstance(r, dict) else r['quoted_status']
            retweeted = r.get('retweeted_status') if isinstance(r, dict) else r['retweeted_status']

            non_original = False

            # 1) in_reply_to_status_id_str 非空
            if in_reply is not None and str(in_reply).strip() != "":
                non_original = True

            # 2) is_quote_status == 1 （兼容字符串/数字/布尔）
            if is_quote is not None:
                try:
                    if int(is_quote) == 1:
                        non_original = True
                except Exception:
                    if str(is_quote).lower() in ("1", "true", "t", "yes"):
                        non_original = True

            # 3) quoted_status 非空
            if quoted is not None and str(quoted).strip() != "":
                non_original = True

            # 4) retweeted_status 非空
            if retweeted is not None and str(retweeted).strip() != "":
                non_original = True

            if non_original:
                # 跳过非原创
                continue

            originals.append(dict(r))

        self.logger.info("加载推文 %d 条，过滤掉 %d 条非原创，保留 %d 条原创", len(rows), len(rows)-len(originals), len(originals))
        return originals

    async def _classify_trading_advice(self, tweet_text: str) -> Dict[str, str]:
        """使用AI分类推文是否包含交易建议 - 修复版本"""
        self.api_call_cnt += 1
        
        # 改进的prompt，明确要求简单的币种名称
        prompt = f"""
Analyze this tweet for cryptocurrency trading advice and mentions.

Tweet: "{tweet_text}"

Return JSON only (no code blocks):
{{
  "has_advice": true/false,
  "crypto_mentions": "comma-separated simple crypto names only",
  "advice_content": "brief trading advice or sentiment"
}}

IMPORTANT for crypto_mentions:
- Use ONLY simple, well-known names: Bitcoin, Ethereum, Solana, BTC, ETH, SOL, USDT, USDC, etc.
- Avoid complex descriptions or project explanations
- If unsure about a name, use the most common form (e.g., "Bitcoin" not "Bitcoin Core")

Trading advice includes:
- Buy/sell recommendations
- Price predictions or targets  
- Investment timing advice
- Market sentiment ("bullish", "bearish", "moon")
- Project enthusiasm implying investment potential
"""
        
        try:
            response = await self.classification_client.chat.completions.create(
                model=CLASSIFICATION_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            content = response.choices[0].message.content.strip()
            
            # 处理可能被代码块包裹的JSON
            if content.startswith("```"):
                import re
                json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1).strip()
                else:
                    content = re.sub(r'```[a-z]*\n?|```', '', content).strip()
            
            try:
                result = json.loads(content)
                has_advice = bool(result.get("has_advice", False))
                crypto_mentions = str(result.get("crypto_mentions", "")).strip()
                advice_content = str(result.get("advice_content", "")).strip()
                
                # 如果提到了加密货币但没有建议，检查隐含的交易情绪
                if crypto_mentions and not has_advice:
                    sentiment_keywords = [
                        "bullish", "bearish", "moon", "rocket", "diamond hands", 
                        "HODL", "hodl", "buy", "sell", "pump", "dump", "dip",
                        "rally", "surge", "crash", "ATH", "ATL", "breakout",
                        "投资", "建议", "推荐", "看好", "看空", "抄底", "出货"
                    ]
                    if any(keyword.lower() in tweet_text.lower() for keyword in sentiment_keywords):
                        has_advice = True
                        advice_content = f"Market sentiment about {crypto_mentions}"
                
                self.logger.debug("推文分类结果: has_advice=%s, crypto_mentions='%s'", 
                                has_advice, crypto_mentions)
                
                return {
                    "has_advice": has_advice,
                    "crypto_mentions": crypto_mentions,
                    "advice_content": advice_content
                }
                
            except json.JSONDecodeError:
                self.logger.error("JSON解析失败，原始响应: %s", content)
                return self._fallback_extraction(tweet_text)
                
        except Exception as e:
            self.logger.error("分类交易建议失败: %s", e)
            return self._fallback_extraction(tweet_text)

    def _fallback_extraction(self, tweet_text: str) -> Dict[str, str]:
        """当AI分类失败时的备用提取方法"""
        # 简单的关键词匹配
        crypto_keywords = [
            "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp", "ripple",
            "dogecoin", "doge", "cardano", "ada", "polygon", "matic", "chainlink",
            "avax", "avalanche", "polkadot", "dot", "shiba", "shib", "usdt", "usdc"
        ]
        
        trading_keywords = [
            "buy", "sell", "hodl", "hold", "moon", "bullish", "bearish", "pump",
            "dump", "dip", "rally", "surge", "invest", "trade", "long", "short",
            "投资", "建议", "推荐", "看好", "看空", "抄底", "出货"
        ]
        
        text_lower = tweet_text.lower()
        
        # 查找加密货币提及
        found_cryptos = []
        for crypto in crypto_keywords:
            if crypto in text_lower:
                # 标准化名称
                if crypto in ["btc", "bitcoin"]:
                    found_cryptos.append("Bitcoin")
                elif crypto in ["eth", "ethereum"]:
                    found_cryptos.append("Ethereum")
                elif crypto in ["sol", "solana"]:
                    found_cryptos.append("Solana")
                else:
                    found_cryptos.append(crypto.title())
        
        # 去重
        found_cryptos = list(set(found_cryptos))
        
        # 查找交易建议
        has_trading_signal = any(keyword in text_lower for keyword in trading_keywords)
        
        return {
            "has_advice": has_trading_signal and len(found_cryptos) > 0,
            "crypto_mentions": ",".join(found_cryptos),
            "advice_content": "Potential trading sentiment detected" if has_trading_signal else ""
        }

    def _split_crypto_names(self, crypto_mentions: str) -> List[str]:
        """分割和标准化加密货币名称"""
        if not crypto_mentions:
            return []
        
        # 标准化分隔符
        normalized = re.sub(r"\s+and\s+|\s*&\s*|\s*,\s*|\s+、\s+|\s+和\s+|\s+or\s+", "|", crypto_mentions)
        
        # 常见币种名称映射
        name_mapping = {
            "btc": "Bitcoin",
            "bitcoin": "Bitcoin", 
            "eth": "Ethereum",
            "ethereum": "Ethereum",
            "sol": "Solana",
            "solana": "Solana",
            "usdt": "USDT",
            "usdc": "USDC",
            "xrp": "XRP",
            "ripple": "XRP",
            "ada": "Cardano",
            "cardano": "Cardano",
            "doge": "Dogecoin",
            "dogecoin": "Dogecoin",
            "matic": "Polygon",
            "polygon": "Polygon",
            "avax": "Avalanche",
            "avalanche": "Avalanche",
            "dot": "Polkadot",
            "polkadot": "Polkadot",
            "link": "Chainlink",
            "chainlink": "Chainlink"
        }
        
        # 分割并标准化
        unique_names = []
        seen = set()
        for name in normalized.split("|"):
            name = name.strip()
            if not name:
                continue
                
            # 移除特殊字符和符号
            cleaned = re.sub(r'[^\w\s]', '', name).strip()
            if not cleaned:
                continue
                
            # 标准化名称
            standardized = name_mapping.get(cleaned.lower(), cleaned.title())
            
            # 只保留看起来像真实币种的名称
            if len(standardized) >= 2 and standardized not in seen:
                unique_names.append(standardized)
                seen.add(standardized)
        
        return unique_names

    async def _save_trade_tweet(self, tweet: Dict, crypto_name: str, advice_content: str, has_advice: bool):
        """保存单条交易推文记录 - 移除coingecko_id"""
        guid = str(uuid.uuid4())
        
        async with self.db_lock:
            self.out_cursor.execute(
                """
                INSERT INTO trade_tweets 
                (guid, tweet_id, author_id, author_name, full_text, created_at,
                 buy_what, advice_content, has_trade_advice)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guid,
                    tweet["tweet_id"],
                    tweet.get("author_id"),
                    tweet.get("author_name"),
                    tweet.get("full_text", ""),
                    tweet.get("created_at"),
                    crypto_name,
                    advice_content,
                    1 if has_advice else 0
                ),
            )
            self.out_conn.commit()

    async def _process_tweet(self, tweet: Dict, sem: asyncio.Semaphore):
        """处理单条推文"""
        async with sem:
            tweet_id = tweet.get("tweet_id")
            tweet_text = tweet.get("full_text", "")
            
            if not tweet_text:
                self.logger.warning("跳过空推文 %s", tweet_id)
                return

            # 分类推文是否包含交易建议
            classification = await self._classify_trading_advice(tweet_text)
            
            has_advice = classification["has_advice"]
            crypto_mentions = classification["crypto_mentions"]
            advice_content = classification["advice_content"]
            
            # 如果没有提到任何加密货币，跳过
            if not crypto_mentions:
                self.logger.debug("推文 %s 未提及加密货币", tweet_id)
                return

            # 提取加密货币名称
            crypto_names = self._split_crypto_names(crypto_mentions)
            
            if not crypto_names:
                self.logger.warning("推文 %s 提及但无法解析加密货币名称", tweet_id)
                return

            self.logger.info("推文 %s: has_advice=%s, 涉及币种: %s", 
                           tweet_id, has_advice, crypto_names)

            # 为每个加密货币创建单独记录
            for crypto_name in crypto_names:
                await self._save_trade_tweet(tweet, crypto_name, advice_content, has_advice)
                
                # 添加短暂延迟避免数据库锁定
                await asyncio.sleep(0.1)

    async def run_async(self):
        """主异步运行函数"""
        self.start_time = time.time()
        tweets = self._load_tweets()
        
        if not tweets:
            self.logger.warning("无推文可处理")
            return

        sem = asyncio.Semaphore(self.max_concurrent)
        tasks = [asyncio.create_task(self._process_tweet(tweet, sem)) for tweet in tweets]

        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 10 == 0:
                elapsed = time.time() - self.start_time
                rate = self.api_call_cnt / elapsed if elapsed else 0
                self.logger.info("进度 %d/%d | API %.1f 次/秒", 
                               done, len(tasks), rate)

        # 生成统计报告
        self._generate_statistics()
        
        # 应用黑名单（如果有）来删除误判为币种的专业术语记录
        try:
            deleted_count = self._apply_blacklist()
            if deleted_count:
                self.logger.info("黑名单清理已删除 %d 条记录", deleted_count)
        except Exception as e:
            self.logger.error("执行黑名单清理时发生错误: %s", e)

        self.out_conn.close()
        self.logger.info("总耗时 %.2fs | API 调用 %d次", 
                        time.time() - self.start_time, self.api_call_cnt)

    def _generate_statistics(self):
        """生成处理统计信息"""
        self.logger.info("\n=== 处理统计 ===")
        
        # 总体统计
        total_records = self.out_cursor.execute("SELECT COUNT(*) FROM trade_tweets").fetchone()[0]
        trade_advice_records = self.out_cursor.execute(
            "SELECT COUNT(*) FROM trade_tweets WHERE has_trade_advice = 1"
        ).fetchone()[0]
        
        self.logger.info("总记录数: %d", total_records)
        self.logger.info("包含交易建议: %d", trade_advice_records)
        self.logger.info("仅提及加密货币: %d", total_records - trade_advice_records)

        # 提及的加密货币统计
        self.logger.info("\n=== 提及的加密货币 TOP10 ===")
        for row in self.out_cursor.execute(
            """
            SELECT buy_what, COUNT(*) as cnt,
                   SUM(has_trade_advice) as advice_count
            FROM trade_tweets
            WHERE buy_what != ''
            GROUP BY buy_what
            ORDER BY cnt DESC
            LIMIT 10
            """
        ):
            self.logger.info("%-15s - %d 次提及 (%d 次建议)", 
                           row[0], row[1], row[2])

        # 作者统计
        self.logger.info("\n=== 活跃作者 TOP5 ===")
        for row in self.out_cursor.execute(
            """
            SELECT author_name, COUNT(*) as cnt,
                   SUM(has_trade_advice) as advice_count
            FROM trade_tweets
            GROUP BY author_name
            ORDER BY cnt DESC
            LIMIT 5
            """
        ):
            self.logger.info("%-20s - %d 条推文 (%d 条建议)", 
                           row[0], row[1], row[2])

    def _normalize_for_compare(self, text: str) -> str:
        """将名称标准化用于比较：删除非字母数字并小写化"""
        if not text:
            return ""
        return re.sub(r"[^0-9a-zA-Z]+", "", text).lower()

    def _load_blacklist(self, path: Optional[str]) -> Set[str]:
        """从给定路径或默认文件加载黑名单，返回规范化后的集合"""
        candidates = []
        if path:
            candidates.append(path)

        # 默认黑名单文件名，优先 db_dir 下的 crypto_blacklist.txt
        candidates.append(os.path.join(self.db_dir, "crypto_blacklist.txt"))
        candidates.append(os.path.join(self.db_dir, "blacklist.txt"))

        found = None
        for p in candidates:
            if p and os.path.isfile(p):
                found = p
                break

        blacklist_set: Set[str] = set()
        if not found:
            self.logger.info("未找到黑名单文件（尝试路径: %s），跳过黑名单清理", candidates)
            return blacklist_set

        try:
            with open(found, "r", encoding="utf-8") as f:
                for line in f:
                    t = line.strip()
                    if not t or t.startswith("#"):
                        continue
                    norm = self._normalize_for_compare(t)
                    if norm:
                        blacklist_set.add(norm)
            self.logger.info("已加载黑名单: %s (%d 项)", found, len(blacklist_set))
        except Exception as e:
            self.logger.error("加载黑名单失败: %s", e)

        return blacklist_set

    def _apply_blacklist(self) -> int:
        """删除 `buy_what` 字段与黑名单匹配的记录，返回删除数量"""
        if not self.blacklist:
            self.logger.debug("黑名单为空，跳过清理")
            return 0

        # 取出所有记录的 guid 和 buy_what
        rows = self.out_cursor.execute("SELECT guid, buy_what FROM trade_tweets WHERE buy_what IS NOT NULL").fetchall()
        to_delete = []
        for guid, buy_what in rows:
            norm = self._normalize_for_compare(buy_what or "")
            if norm in self.blacklist:
                to_delete.append(guid)

        if not to_delete:
            self.logger.info("未发现匹配黑名单的记录，跳过删除")
            return 0

        # 批量删除
        deleted = 0
        try:
            for g in to_delete:
                self.out_cursor.execute("DELETE FROM trade_tweets WHERE guid = ?", (g,))
                deleted += 1
            self.out_conn.commit()
            self.logger.info("已删除 %d 条与黑名单匹配的记录", deleted)
        except Exception as e:
            self.logger.error("删除黑名单记录时出错: %s", e)
            self.out_conn.rollback()

        return deleted

    def run(self):
        """同步入口函数"""
        asyncio.run(self.run_async())

def main():
    parser = argparse.ArgumentParser(description="从推文中识别交易建议并生成guid_to_trade_tweet.db (修复版本)")
    parser.add_argument("--db_dir", default=".", help="数据库文件夹 (含 tweets.db)")
    parser.add_argument("--api_key", required=True, help="OpenAI API Key")
    parser.add_argument("--max_concurrent", type=int, default=MAX_CONCURRENT,
                       help=f"最大并发数 (默认 {MAX_CONCURRENT})")
    parser.add_argument("--blacklist", default=None, help="可选的黑名单文件路径（每行一个词），或在 db_dir 中放 crypto_blacklist.txt")
    args = parser.parse_args()

    generator = TradeTweetGenerator(args.db_dir, args.api_key, args.max_concurrent, blacklist_path=args.blacklist)
    generator.run()

if __name__ == "__main__":
    main()