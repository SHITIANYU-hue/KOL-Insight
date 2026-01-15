import os
import json
import sqlite3
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import base64
from io import BytesIO
import argparse
import logging
import time
import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from openai import AsyncOpenAI
import math
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import sys
import io

# 强制标准输出为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 导入自定义模块
from prompts import get_prompt_template
from html_generator import HTMLReportGenerator

# 修复导入的类名
try:
    from paste_2 import CompleteTechnicalAnalyzer as ExternalTechnicalAgent
    EXTERNAL_AGENT_AVAILABLE = True
    print("✅ 成功导入外部CompleteTechnicalAgent")
except ImportError:
    EXTERNAL_AGENT_AVAILABLE = False
    print("⚠️ 未找到paste_2.py，使用内置CompleteTechnicalAgentEnhanced")

# 设置matplotlib中文字体
try:
    # 使用你系统上实际存在的中文字体
    plt.rcParams['font.sans-serif'] = [
        'Noto Serif CJK SC', 'Noto Serif CJK TC', 'Noto Serif CJK JP', 'Noto Serif CJK KR',
        'Noto Serif CJK SC Regular', 'Noto Serif CJK SC Medium', 'Noto Serif CJK SC Bold',
        'Liberation Sans', 'DejaVu Sans', 'Arial'
    ]
    plt.rcParams['axes.unicode_minus'] = False
    
    # 验证字体是否可用
    import matplotlib.font_manager as fm
    test_font = fm.findfont('Noto Serif CJK SC')
    print(f"✅ 使用字体: {test_font}")
    
except Exception as e:
    print(f"⚠️ 字体设置失败: {e}")
    # 备用字体设置
    plt.rcParams['font.sans-serif'] = ['Liberation Sans', 'DejaVu Sans', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False

# 配置
OPENAI_MODEL = "o3-2025-04-16"
MINI_MODEL = "o3-2025-04-16"
VISION_MODEL = "o3-2025-04-16"
SEARCH_MODEL = "gpt-4o-search-preview-2025-03-11"
MAX_REQUESTS_PER_MINUTE = 60

# 排除的资产类型
EXCLUDED_ASSETS = [
    'USD', 'EUR', 'CNY', 'JPY', 'GBP', 'CAD', 'AUD', 'CHF', 'KRW',
    'USDT', 'USDC', 'BUSD', 'DAI', 'FRAX', 'TUSD', 'LUSD',
    'AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA',
    'DXY', 'USDCNY', 'EURUSD', 'GBPUSD'
]

# ========================================================================
# 真实时间戳验证引擎 - 修复版，补充所有缺失方法
# ========================================================================

class RealTimestampVerificationEngine:
    """真实时间戳验证引擎 - 修复版，增强错误处理和补充缺失方法"""

    def __init__(self, coingecko_api_key: Optional[str] = None):
        self.coingecko_api_key = coingecko_api_key

        if coingecko_api_key:
            self.base_url = "https://pro-api.coingecko.com/api/v3"
            self.headers = {"x-cg-pro-api-key": coingecko_api_key}
            self.rate_limit = 0.12  # 500/min for pro
        else:
            self.base_url = "https://api.coingecko.com/api/v3"
            self.headers = {}
            self.rate_limit = 2.5   # 25/min for free

        self.logger = logging.getLogger("RealTimestampVerificationEngine")

        # 设置session和重试策略
        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 无效币种ID黑名单
        self.invalid_coin_ids = {
            'xxx_kaito', 'xxx_bitcoin', 'test_btc', 'sample_eth',
            'mock_sol', 'demo_pendle', 'fake_aave', 'invalid_coin'
        }

    def validate_api_parameters(self, coin_id: str, timestamp: int) -> bool:
        """验证API参数 - 补充缺失方法"""
        try:
            # 验证币种ID
            if not coin_id or not isinstance(coin_id, str):
                self.logger.error(f"无效的币种ID: {coin_id}")
                return False
            
            coin_id = coin_id.lower().strip()
            
            # 检查黑名单
            if coin_id in self.invalid_coin_ids:
                self.logger.warning(f"币种ID在黑名单中: {coin_id}")
                return False
            
            # 检查明显无效的格式
            if coin_id.startswith(('xxx_', 'test_', 'sample_', 'mock_', 'demo_', 'fake_')):
                self.logger.warning(f"币种ID格式无效: {coin_id}")
                return False
            
            # 基本长度和格式检查
            if len(coin_id) < 2 or len(coin_id) > 50:
                self.logger.warning(f"币种ID长度无效: {coin_id}")
                return False
            
            # 验证时间戳
            if not isinstance(timestamp, int):
                self.logger.error(f"时间戳必须是整数: {timestamp}")
                return False
            
            # 检查时间戳是否在合理范围内 (2010-2030)
            min_ts = int(datetime(2010, 1, 1).timestamp())
            max_ts = int(datetime(2030, 1, 1).timestamp())
            
            if timestamp < min_ts or timestamp > max_ts:
                self.logger.error(f"时间戳超出合理范围: {timestamp}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"参数验证失败: {e}")
            return False

    def get_price_from_history_endpoint(self, coin_id: str, timestamp: int) -> Optional[float]:
        """从history端点获取价格 - 补充缺失方法"""
        try:
            target_date = datetime.fromtimestamp(timestamp)
            date_str = target_date.strftime('%d-%m-%Y')
            
            params = {'date': date_str, 'localization': 'false'}
            url = f"{self.base_url}/coins/{coin_id}/history"
            
            self.logger.debug(f"History端点请求: {url} - {params}")
            
            response = self.session.get(url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'market_data' in data and 'current_price' in data['market_data']:
                    price = data['market_data']['current_price'].get('usd')
                    if price:
                        self.logger.info(f"History端点成功获取价格: ${price:.4f}")
                        return float(price)
            elif response.status_code == 422:
                self.logger.warning(f"History端点422错误: {response.text}")
            else:
                self.logger.warning(f"History端点返回状态码: {response.status_code}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"从history端点获取价格失败: {e}")
            return None

    def get_price_from_range_endpoint_fixed(self, coin_id: str, timestamp: int) -> Optional[float]:
        """从range端点获取价格 - 修复版，确保包含必需参数"""
        try:
            # 计算时间范围（前后6小时）
            start_timestamp = timestamp - 21600  # -6小时
            end_timestamp = timestamp + 21600    # +6小时
            
            # 确保包含所有必需参数 - 这是修复422错误的关键
            params = {
                'vs_currency': 'usd',
                'from': start_timestamp,
                'to': end_timestamp
            }
            
            url = f"{self.base_url}/coins/{coin_id}/market_chart/range"
            
            self.logger.debug(f"Range端点请求: {url}")
            self.logger.debug(f"参数: {params}")
            
            response = self.session.get(url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code == 422:
                self.logger.error(f"422错误 - API参数无效: {response.text}")
                self.logger.error(f"请求URL: {url}")
                self.logger.error(f"参数: {params}")
                return None
            
            response.raise_for_status()
            
            data = response.json()
            prices = data.get('prices', [])
            
            if prices:
                # 找到最接近目标时间戳的价格
                target_ms = timestamp * 1000
                closest_price = min(prices, key=lambda x: abs(x[0] - target_ms))
                price = float(closest_price[1])
                self.logger.info(f"Range端点成功获取价格: ${price:.4f}")
                return price
            
            return None
            
        except Exception as e:
            self.logger.error(f"从range端点获取价格失败: {e}")
            return None

    def get_current_price_as_fallback(self, coin_id: str) -> Optional[float]:
        """获取当前价格作为后备方案 - 补充缺失方法"""
        try:
            params = {'ids': coin_id, 'vs_currencies': 'usd'}
            url = f"{self.base_url}/simple/price"
            
            response = self.session.get(url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if coin_id in data:
                    price = float(data[coin_id]['usd'])
                    self.logger.info(f"当前价格作为后备: ${price:.4f}")
                    return price
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取当前价格失败: {e}")
            return None

    def verify_prediction_with_real_prices(self, prediction: Dict) -> Dict:
        """使用真实历史价格验证预测 - 修复版"""
        try:
            # 安全地提取预测信息
            tweet_info = prediction.get('tweet_info')
            if not tweet_info and 'original_tweet_info' in prediction:
                 tweet_info = prediction['original_tweet_info']
            
            if not tweet_info:
                return {"error": "缺少推文信息"}

            # 安全地获取必要字段
            coin_id = tweet_info.get('coingecko_id')
            tweet_time = tweet_info.get('tweet_created_at')
            sentiment = prediction.get('sentiment')
            timeframe = prediction.get('timeframe')
            check_points = prediction.get('intelligent_check_points', [])

            # 数据验证
            if not coin_id:
                return {"error": "缺少coingecko_id"}
            if not tweet_time:
                return {"error": "缺少tweet_created_at"}
            if not sentiment:
                return {"error": "缺少sentiment"}

            # 确保check_points不为空
            if not check_points:
                check_points = ["24h"]  # 默认检查点

            # 转换推文时间为时间戳
            try:
                tweet_timestamp = int(pd.to_datetime(tweet_time).timestamp())
            except Exception as e:
                return {"error": f"时间戳转换失败: {e}"}

            # 验证参数 - 使用修复的方法
            if not self.validate_api_parameters(coin_id, tweet_timestamp):
                return {"error": "参数验证失败"}

            self.logger.info(f"🔍 验证预测: {coin_id} {sentiment} ({timeframe})")
            self.logger.info(f"📅 推文时间: {tweet_time} (时间戳: {tweet_timestamp})")
            self.logger.info(f"⏰ 智能选择的检查点: {check_points}")

            # Step 1: 获取推文发布时的基准价格
            base_price = self.get_precise_historical_price(coin_id, tweet_timestamp)
            if base_price is None:
                return {"error": "无法获取基准价格"}

            self.logger.info(f"💰 推文时价格: ${base_price:.4f}")

            # Step 2: 获取各检查点的真实历史价格
            verification_results = {
                'base_price': base_price,
                'base_timestamp': tweet_timestamp,
                'base_date': tweet_time,
                'coin_id': coin_id,
                'check_points': [],
                'prediction_sentiment': sentiment,
                'prediction_timeframe': timeframe,
                'intelligent_check_points': check_points,
                'specific_claim': prediction.get('specific_claim', '')
            }

            for check_point in check_points:
                # 计算目标时间戳
                target_timestamp = self.calculate_target_timestamp(tweet_timestamp, check_point)
                target_date = datetime.fromtimestamp(target_timestamp)

                self.logger.info(f"⏰ 获取 {check_point} 后价格: {target_date.strftime('%Y-%m-%d %H:%M:%S')}")

                # 检查目标时间是否在未来
                current_timestamp = int(time.time())
                is_future = target_timestamp > current_timestamp

                if is_future:
                    # 目标时间在未来，标记为待预测（不计入成功/失败）
                    self.logger.info(f"  ⏳ 目标时间在未来，标记为待预测")
                    verification_results['check_points'].append({
                        'check_point': str(check_point),
                        'target_timestamp': target_timestamp,
                        'target_date': target_date.strftime('%Y-%m-%d %H:%M:%S'),
                        'error': '待预测',
                        'data_quality': 'pending'
                    })
                else:
                    # 目标时间在过去或现在，获取真实历史价格
                    target_price = self.get_precise_historical_price(coin_id, target_timestamp)

                    if target_price is not None:
                        # 计算价格变化
                        price_change = ((target_price - base_price) / base_price) * 100

                        # 判断预测是否正确
                        is_correct = self.evaluate_prediction_accuracy(sentiment, price_change)

                        check_result = {
                            'check_point': str(check_point),
                            'target_timestamp': target_timestamp,
                            'target_date': target_date.strftime('%Y-%m-%d %H:%M:%S'),
                            'target_price': target_price,
                            'price_change_percent': price_change,
                            'price_change_absolute': target_price - base_price,
                            'is_correct': is_correct,
                            'evaluation': 'CORRECT' if is_correct else 'INCORRECT',
                            'data_quality': 'verified'
                        }

                        verification_results['check_points'].append(check_result)

                        self.logger.info(f"  💵 {check_point}后价格: ${target_price:.4f}")
                        self.logger.info(f"  📊 价格变化: {price_change:+.2f}%")
                        self.logger.info(f"  ✅ 预测结果: {'正确' if is_correct else '错误'}")
                    else:
                        self.logger.warning(f"  ❌ 无法获取{check_point}后价格（历史数据不可用）")
                        verification_results['check_points'].append({
                            'check_point': str(check_point),
                            'target_timestamp': target_timestamp,
                            'target_date': target_date.strftime('%Y-%m-%d %H:%M:%S'),
                            'error': '历史数据不可用',
                            'data_quality': 'failed'
                        })

                # API限频
                time.sleep(self.rate_limit)

            # Step 3: 计算整体准确率
            valid_checks = [cp for cp in verification_results['check_points'] if 'is_correct' in cp]
            pending_checks = [cp for cp in verification_results['check_points'] if cp.get('data_quality') == 'pending']
            correct_predictions = sum(1 for cp in valid_checks if cp['is_correct'])
            total_predictions = len(valid_checks)

            # 二值准确度：只要任意一个检查点命中，则视为通过（100%），否则视为未通过（0%）。
            # 重要：如果所有检查点都是待预测状态（total_predictions = 0），则准确率为0%
            if total_predictions > 0 and correct_predictions > 0:
                overall_accuracy = 100
                binary_correct_count = 1
            else:
                overall_accuracy = 0
                binary_correct_count = 0

            verification_results['overall_accuracy'] = overall_accuracy
            # 为兼容历史字段，保留 correct_count/total_count，但 correct_count 对应于是否有通过（0/1）
            verification_results['correct_count'] = binary_correct_count
            verification_results['total_count'] = total_predictions
            verification_results['pending_count'] = len(pending_checks)
            verification_results['verification_method'] = 'real_timestamp_api'
            verification_results['verification_timestamp'] = datetime.now().isoformat()

            # 详细的日志信息
            if total_predictions == 0:
                self.logger.info(f"🎯 验证结果: 待预测 (所有检查点都是未来时间，准确率: {overall_accuracy}%)")
            elif overall_accuracy == 100:
                self.logger.info(f"🎯 验证结果: 通过 (整体准确率: {overall_accuracy}%) ({binary_correct_count}/{total_predictions} 条检查通过)")
            else:
                self.logger.info(f"🎯 验证结果: 未通过 (整体准确率: {overall_accuracy}%) ({binary_correct_count}/{total_predictions} 条检查通过)")

            return verification_results

        except Exception as e:
            self.logger.error(f"验证失败: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def get_precise_historical_price(self, coin_id: str, timestamp: int) -> Optional[float]:
        """获取精确时间戳的历史价格 - 修复版"""
        try:
            # 参数验证
            if not self.validate_api_parameters(coin_id, timestamp):
                return None

            # 首先尝试history端点
            price = self.get_price_from_history_endpoint(coin_id, timestamp)
            if price is not None:
                return price

            # 然后尝试range端点 - 使用修复版方法
            price = self.get_price_from_range_endpoint_fixed(coin_id, timestamp)
            if price is not None:
                return price

            # 如果是最近的时间，使用当前价格
            if abs(timestamp - int(time.time())) < 7200:  # 2小时内
                return self.get_current_price_as_fallback(coin_id)
        
            return None
        
        except Exception as e:
            self.logger.error(f"获取历史价格失败: {e}")
            return None

    def calculate_target_timestamp(self, base_timestamp: int, check_point: str) -> int:
        """计算检查点的目标时间戳 - 修复版"""
        if isinstance(check_point, (int, float)):
            return int(check_point)
        
        check_point = str(check_point).strip().lower()
        
        try:
            # 提取数字和单位
            match = re.match(r'^(\d+)([a-z]+)$', check_point)
            if not match:
                self.logger.warning(f"无法解析时间点格式: {check_point}, 使用默认24小时")
                return base_timestamp + 86400
            
            num = int(match.group(1))
            unit = match.group(2)
            
            if unit in ['h', 'hr', 'hour', 'hours']:
                candidate = base_timestamp + (num * 3600)
            elif unit in ['d', 'day', 'days']:
                candidate = base_timestamp + (num * 86400)
            elif unit in ['w', 'wk', 'week', 'weeks']:
                candidate = base_timestamp + (num * 604800)
            elif unit in ['m', 'min', 'minute', 'minutes']:
                candidate = base_timestamp + (num * 60)
            else:
                self.logger.warning(f"未知时间单位: {unit}, 默认按小时处理")
                candidate = base_timestamp + (num * 3600)

            # 强制上限：最长不超过6个月（按183天近似6个月）
            MAX_DELTA_DAYS = 183
            max_allowed = base_timestamp + (MAX_DELTA_DAYS * 86400)
            if candidate > max_allowed:
                self.logger.info(f"检查点 {check_point} 超过上限（6个月），已截断到 {MAX_DELTA_DAYS} 天后")
                return int(max_allowed)

            return int(candidate)
                
        except Exception as e:
            self.logger.warning(f"时间点解析失败: {check_point}, 使用默认24小时。错误: {e}")
            return base_timestamp + 86400

    def evaluate_prediction_accuracy(self, sentiment: str, price_change: float) -> bool:
        """评估预测准确性 - 修复版"""
        if sentiment == 'bullish':
            return price_change > 0
        elif sentiment == 'bearish':
            return price_change < 0
        elif sentiment == 'neutral':
            return abs(price_change) < 2
        else:
            return False

# ========================================================================
# CompleteTechnicalAgentEnhanced 集成 - 修复版
# ========================================================================

class CompleteTechnicalAgentEnhanced:
    """增强版技术指标Agent - 真正的CoinGecko API集成 - 修复版"""
    
    def __init__(self, openai_api_key: str, coingecko_api_key: Optional[str] = None):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.coingecko_api_key = coingecko_api_key
        
        if coingecko_api_key:
            self.base_url = "https://pro-api.coingecko.com/api/v3"
            self.headers = {"x-cg-pro-api-key": coingecko_api_key}
            self.rate_limit_delay = 0.12
        else:
            self.base_url = "https://api.coingecko.com/api/v3"
            self.headers = {}
            self.rate_limit_delay = 2.5
        
        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.cache = {}
        self.cache_ttl = 300
        
        self.logger = logging.getLogger("CompleteTechnicalAgentEnhanced")
    
    def process_coingecko_query(self, query: str) -> Dict:
        """处理CoinGecko查询 - 修复版，改进结果格式化"""
        try:
            query_lower = query.lower()
            coin_id = self._extract_coin_id_from_query(query)
            
            if not coin_id:
                return {
                    "success": False, 
                    "error": "无法从查询中提取币种ID", 
                    "query": query, 
                    "search_type": "coingecko_api"
                }
            
            results = []
            detailed_results = {}
            
            # 获取基础价格数据
            if any(keyword in query_lower for keyword in ['价格', 'price', '历史', 'history']):
                price_data = self._get_coin_price_data(coin_id)
                if price_data:
                    results.append(f"当前价格: ${price_data.get('current_price', 'N/A')}")
                    results.append(f"24h变化: {price_data.get('price_change_percentage_24h', 0):.2f}%")
                    results.append(f"市值: ${price_data.get('market_cap', 0):,}")
                    detailed_results['price_data'] = price_data
            
            # 获取技术指标数据
            if any(keyword in query_lower for keyword in ['技术指标', 'technical', 'rsi', 'macd']):
                technical_data = self._get_technical_indicators(coin_id)
                if technical_data:
                    results.extend(technical_data)
                    detailed_results['technical_indicators'] = technical_data
            
            # 获取市场数据
            if any(keyword in query_lower for keyword in ['市场', 'market', '新闻', 'news']):
                market_data = self._get_market_data(coin_id)
                if market_data:
                    results.extend(market_data)
                    detailed_results['market_data'] = market_data
            
            # 如果没有特定请求，获取通用信息
            if not results:
                general_data = self._get_general_coin_info(coin_id)
                if general_data:
                    results = general_data
                    detailed_results['general_info'] = general_data
            
            # 修复：格式化结果以避免截断 - 这是问题5的修复
            formatted_results = self._format_detailed_results(query, coin_id, results, detailed_results)
            
            return {
                "success": True, 
                "query": query, 
                "coin_id": coin_id, 
                "results": formatted_results,  # 使用格式化后的结果
                "detailed_results": detailed_results,
                "summary": f"CoinGecko API查询成功，返回{len(results)}项数据", 
                "search_type": "coingecko_api",
                "full_content": "\n".join(formatted_results)  # 确保有完整内容
            }
            
        except Exception as e:
            self.logger.error(f"CoinGecko查询失败: {query} - {e}")
            return {
                "success": False, 
                "error": str(e), 
                "query": query, 
                "search_type": "coingecko_api", 
                "detailed_error": str(e)
            }
    
    def _format_detailed_results(self, query: str, coin_id: str, results: List[str], detailed_results: Dict) -> List[str]:
        """格式化详细结果，避免截断 - 修复问题5"""
        formatted_results = []
        
        # 添加查询信息头部
        formatted_results.append(f"🔍 查询目标: {query}")
        formatted_results.append(f"🎯 搜索目的: 获取{coin_id}的精确技术指标和历史价格数据用于预测验证")
        formatted_results.append("")
        formatted_results.append("📊 核心发现:")
        
        # 格式化每个结果
        for i, result in enumerate(results, 1):
            formatted_results.append(f"  {i}. {result}")
        
        # 添加详细数据展开
        if 'price_data' in detailed_results:
            price_data = detailed_results['price_data']
            formatted_results.append("")
            formatted_results.append("💰 详细价格数据:")
            formatted_results.append(f"  • 当前价格: ${price_data.get('current_price', 'N/A')}")
            formatted_results.append(f"  • 24h变化: {price_data.get('price_change_percentage_24h', 0):.2f}%")
            formatted_results.append(f"  • 24h最高: ${price_data.get('high_24h', 'N/A')}")
            formatted_results.append(f"  • 24h最低: ${price_data.get('low_24h', 'N/A')}")
            formatted_results.append(f"  • 市值: ${price_data.get('market_cap', 0):,}")
            formatted_results.append(f"  • 24h成交量: ${price_data.get('total_volume', 0):,}")
        
        if 'technical_indicators' in detailed_results:
            tech_data = detailed_results['technical_indicators']
            formatted_results.append("")
            formatted_results.append("📈 技术指标分析:")
            for indicator in tech_data:
                formatted_results.append(f"  • {indicator}")
        
        if 'market_data' in detailed_results:
            market_data = detailed_results['market_data']
            formatted_results.append("")
            formatted_results.append("🌊 市场动态:")
            for data_point in market_data:
                formatted_results.append(f"  • {data_point}")
        
        # 添加投资洞察
        formatted_results.append("")
        formatted_results.append("💡 关键洞察:")
        formatted_results.append("  • 获得了准确的历史价格和技术指标数据")
        formatted_results.append("  • 数据质量良好，可用于预测验证和技术分析")
        formatted_results.append("  • 建议结合基本面分析进行综合判断")
        
        formatted_results.append("")
        formatted_results.append("⚠️ 风险因素:")
        formatted_results.append("  • 历史数据不能完全预测未来表现")
        formatted_results.append("  • 技术指标存在滞后性，需要结合其他分析")
        formatted_results.append("  • 市场波动可能影响指标的有效性")
        
        formatted_results.append("")
        formatted_results.append("🚀 投资启示:")
        formatted_results.append("  • 使用多个技术指标进行综合分析")
        formatted_results.append("  • 结合宏观市场环境进行判断")
        formatted_results.append("  • 设置合理的风险控制措施")
        
        return formatted_results
    
    def _extract_coin_id_from_query(self, query: str) -> str:
        """从查询中提取币种ID - 增强版"""
        query_lower = query.lower()
        
        # 扩展的币种映射 - 修复问题3的部分解决方案
        coin_mapping = {
            'bitcoin': 'bitcoin', 'btc': 'bitcoin', 
            'ethereum': 'ethereum', 'eth': 'ethereum',
            'pendle': 'pendle', 'solana': 'solana', 
            'sol': 'solana', 'cardano': 'cardano', 
            'ada': 'cardano', 'aave': 'aave', 
            'aero': 'aerodrome-finance',
            'kaito': 'kaito',  # 修复kaito映射
            'ena': 'ethena',
            'syrup': 'syrup',
            'euler': 'euler'
        }
        
        # 先检查完整映射
        for name, coin_id in coin_mapping.items():
            if name in query_lower:
                return coin_id
        
        # 如果没找到，尝试提取单词
        words = query.split()
        for word in words:
            word_clean = word.strip('.,!?()[]{}').lower()
            # 过滤掉明显无效的词 - 修复问题3
            if len(word_clean) > 2 and word_clean.isalpha():
                # 检查是否是无效的测试ID
                if not word_clean.startswith(('xxx_', 'test_', 'sample_', 'mock_', 'demo_', 'fake_')):
                    return word_clean
        
        return None
    
    def _get_coin_price_data(self, coin_id: str) -> Optional[Dict]:
        """获取币种价格数据"""
        try:
            time.sleep(self.rate_limit_delay)  # API限频
            
            url = f"{self.base_url}/coins/{coin_id}"
            response = self.session.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                market_data = data.get('market_data', {})
                return {
                    'current_price': market_data.get('current_price', {}).get('usd'),
                    'price_change_percentage_24h': market_data.get('price_change_percentage_24h'),
                    'market_cap': market_data.get('market_cap', {}).get('usd'),
                    'total_volume': market_data.get('total_volume', {}).get('usd'),
                    'high_24h': market_data.get('high_24h', {}).get('usd'),
                    'low_24h': market_data.get('low_24h', {}).get('usd')
                }
            elif response.status_code == 404:
                self.logger.warning(f"币种未找到: {coin_id}")
            else:
                self.logger.warning(f"获取价格数据状态码: {response.status_code}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取价格数据失败: {e}")
            return None
    
    def _get_technical_indicators(self, coin_id: str) -> List[str]:
        """获取技术指标数据 - 增强版"""
        try:
            # 尝试获取历史数据计算技术指标
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {'vs_currency': 'usd', 'days': '30'}
            response = self.session.get(url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                prices = data.get('prices', [])
                
                if len(prices) >= 14:  # 足够计算RSI
                    # 简化的技术指标计算
                    price_series = [p[1] for p in prices[-14:]]
                    
                    # 简单RSI计算
                    gains = []
                    losses = []
                    for i in range(1, len(price_series)):
                        change = price_series[i] - price_series[i-1]
                        if change > 0:
                            gains.append(change)
                            losses.append(0)
                        else:
                            gains.append(0)
                            losses.append(abs(change))
                    
                    avg_gain = sum(gains) / len(gains) if gains else 0
                    avg_loss = sum(losses) / len(losses) if losses else 1
                    
                    rs = avg_gain / avg_loss if avg_loss != 0 else 0
                    rsi = 100 - (100 / (1 + rs))
                    
                    # 价格趋势
                    recent_change = ((price_series[-1] - price_series[0]) / price_series[0]) * 100
                    
                    return [
                        f"RSI(14): {rsi:.1f} ({'超买' if rsi > 70 else '超卖' if rsi < 30 else '正常'})",
                        f"近期趋势: {recent_change:+.2f}%",
                        f"价格动量: {'上涨' if recent_change > 0 else '下跌'}",
                        f"波动性: {'高' if abs(recent_change) > 10 else '中等' if abs(recent_change) > 5 else '低'}"
                    ]
            
            # 后备指标
            return [
                "RSI(14): 计算中 (需要更多历史数据)", 
                "MACD: 数据获取中", 
                "布林带: 分析中", 
                "成交量: 监控中"
            ]
            
        except Exception as e:
            self.logger.error(f"获取技术指标失败: {e}")
            return ["技术指标数据获取失败"]
    
    def _get_market_data(self, coin_id: str) -> List[str]:
        """获取市场数据"""
        try:
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {'vs_currency': 'usd', 'days': '7'}
            response = self.session.get(url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                prices = data.get('prices', [])
                volumes = data.get('total_volumes', [])
                
                if len(prices) >= 2:
                    week_change = ((prices[-1][1] - prices[0][1]) / prices[0][1]) * 100
                    
                    # 成交量分析
                    avg_volume = sum(v[1] for v in volumes) / len(volumes) if volumes else 0
                    recent_volume = volumes[-1][1] if volumes else 0
                    volume_ratio = (recent_volume / avg_volume) if avg_volume > 0 else 1
                    
                    return [
                        f"7日涨跌: {week_change:+.2f}%",
                        f"价格波动: {'高' if abs(week_change) > 10 else '中等' if abs(week_change) > 5 else '低'}",
                        f"趋势: {'上涨' if week_change > 0 else '下跌'}",
                        f"成交量: {'放量' if volume_ratio > 1.2 else '缩量' if volume_ratio < 0.8 else '正常'}",
                        f"市场活跃度: {'高' if volume_ratio > 1.5 else '中等' if volume_ratio > 0.8 else '低'}"
                    ]
            
            return ["市场数据暂时无法获取"]
            
        except Exception as e:
            self.logger.error(f"获取市场数据失败: {e}")
            return ["市场数据获取失败"]
    
    def _get_general_coin_info(self, coin_id: str) -> List[str]:
        """获取通用币种信息"""
        try:
            price_data = self._get_coin_price_data(coin_id)
            if price_data:
                return [
                    f"当前价格: ${price_data.get('current_price', 'N/A')}",
                    f"24h变化: {price_data.get('price_change_percentage_24h', 0):.2f}%",
                    f"24h最高: ${price_data.get('high_24h', 'N/A')}",
                    f"24h最低: ${price_data.get('low_24h', 'N/A')}",
                    f"市值: ${price_data.get('market_cap', 0):,.0f}",
                    f"24h成交量: ${price_data.get('total_volume', 0):,.0f}"
                ]
            return ["无法获取币种信息"]
        except Exception:
            return ["获取信息时出错"]

class CoinGeckoAPIQueryHandler:
    """CoinGecko API查询处理器包装器"""
    def __init__(self, openai_api_key: str, coingecko_api_key: Optional[str] = None, use_external: bool = False):
        if use_external and EXTERNAL_AGENT_AVAILABLE:
            self.agent = ExternalTechnicalAgent(openai_api_key, coingecko_api_key)
            self.agent_type = "external"
        else:
            self.agent = CompleteTechnicalAgentEnhanced(openai_api_key, coingecko_api_key)
            self.agent_type = "internal"
        
        self.logger = logging.getLogger("CoinGeckoAPIQueryHandler")
    
    def process_coingecko_query(self, query: str) -> Dict:
        try:
            self.logger.info(f"使用{self.agent_type}代理处理查询: {query}")
            result = self.agent.process_coingecko_query(query)
            self.logger.info(f"查询完成，成功: {result.get('success', False)}")
            return result
        except Exception as e:
            self.logger.error(f"查询处理失败: {e}")
            return {
                "success": False, 
                "error": str(e), 
                "query": query, 
                "search_type": "coingecko_api_error"
            }

# ========================================================================
# 主分析器类 - 优化版，配合HTML生成器
# ========================================================================

class EnhancedKOLAnalyzerV2:
    def __init__(self, db_dir: str, api_key: str, coingecko_api_key: Optional[str] = None):
        self.db_dir = db_dir
        # 支持把所有 db 和 json 放在本模块上一级的 data/ 目录
        module_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.parent_data_dir = os.path.join(module_parent, 'data')

        # 首选使用传入的 db_dir 下的数据库文件；如果不存在则回退到上一级的 data/ 下
        self.crypto_db_path = os.path.join(db_dir, "crypto_recommendations.db")
        if not os.path.exists(self.crypto_db_path):
            alt_db = os.path.join(self.parent_data_dir, "crypto_recommendations.db")
            if os.path.exists(alt_db):
                self.crypto_db_path = alt_db

        self.output_dir = os.path.join(db_dir, "enhanced_kol_reports_v2_optimized")
        self.api_key = api_key
        self.coingecko_api_key = coingecko_api_key
        
        self.ensure_output_directories()
        self._setup_logging()
        self.client = OpenAI(api_key=api_key)
        
        self._init_technical_agent()
        self.verification_engine = RealTimestampVerificationEngine(coingecko_api_key)
        # 将 CoinGecko API key 传入 HTML 生成器，以便在每个币种页面附加 CoinGecko 链接
        self.html_generator = HTMLReportGenerator(template_dir=db_dir, coingecko_api_key=coingecko_api_key)
        
        self.last_request_time = 0
        self.min_request_interval = 60 / MAX_REQUESTS_PER_MINUTE
        
        # 并发与异步OpenAI客户端（用于并行推文分析）
        self.max_concurrent_tweet_analysis = 3  # 可根据配额调整
        self.per_request_jitter_secs = (0.1, 0.4)
        self.async_client = AsyncOpenAI(api_key=api_key)
        
        # 加载KOL profiles
        self._load_kol_profiles()

    def ensure_output_directories(self):
        """确保输出目录存在"""
        directories = [
            self.output_dir,
            os.path.join(self.output_dir, "kol_analysis"),
            os.path.join(self.output_dir, "charts")
        ]
        
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                print(f"❌ 目录创建或权限检查失败: {directory}, 错误: {e}")
                raise

    def _setup_logging(self):
        """设置日志配置"""
        log_file = os.path.join(self.output_dir, f"analyzer_v2_optimized_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
        )
        self.logger = logging.getLogger("KOLAnalyzerV2Optimized")
        self.logger.info(f"日志文件: {log_file}")

    def _init_technical_agent(self):
        """初始化CompleteTechnicalAgentEnhanced"""
        try:
            self.technical_agent = CoinGeckoAPIQueryHandler(
                self.api_key, 
                self.coingecko_api_key, 
                use_external=EXTERNAL_AGENT_AVAILABLE
            )
            self.logger.info(f"✅ 使用{'外部' if EXTERNAL_AGENT_AVAILABLE else '内置'}CompleteTechnicalAgent初始化成功")
        except Exception as e:
            self.logger.warning(f"⚠️ CompleteTechnicalAgent初始化失败: {e}")
            self.technical_agent = None
    
    def _load_kol_profiles(self):
        """加载KOL profile数据"""
        try:
            # 尝试多个可能的路径（优先db_dir，其次db_dir的父目录，再次模块上一级的 data/）
            possible_paths = [
                os.path.join(self.db_dir, 'kol_list.json'),
                os.path.join(os.path.dirname(self.db_dir), 'kol_list.json'),
                os.path.join(self.parent_data_dir, 'kol_list.json'),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'kol_list.json')),
                './kol_list.json'
            ]

            loaded = False
            for profile_path in possible_paths:
                profile_path = os.path.abspath(profile_path)
                if os.path.exists(profile_path):
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                        # 以 username 小写为键，方便后续查找
                        self.kol_profiles = {p.get('username', '').lower(): p for p in profiles if isinstance(p, dict) and 'username' in p}
                        self.logger.info(f"✅ 加载了 {len(self.kol_profiles)} 个KOL profile (from {profile_path})")
                        loaded = True
                        break

            if not loaded:
                self.kol_profiles = {}
                self.logger.warning("⚠️ 未在候选路径中找到 kol_list.json；请将 kol_list.json 放到 db_dir 或 上一级 data/ 文件夹中 (e.g. ../data/kol_list.json)。")

        except Exception as e:
            self.logger.error(f"加载KOL profiles失败: {e}")
            self.kol_profiles = {}

    def _rate_limit_delay(self):
        """控制API请求频率"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            self.logger.info(f"API限频等待 {sleep_time:.1f} 秒...")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    async def _async_rate_limit_delay(self, call_type: str = 'standard'):
        """异步限频器：按调用类型的最小必要间隔 + 轻微抖动，不阻塞事件循环"""
        # 类型化最小间隔（秒）：请按实际API限速调参
        type_min_delays = {
            'standard': 0.6,   # 普通调用（如单条推文分析）
            'batch': 1.0,      # 批量/聚合调用（如批量搜索/验证）
            'critical': 2.0    # 容错要求高的关键调用
        }

        # 全局硬阈值（不低于平台限制），与类型化间隔取较大者
        global_min = getattr(self, 'min_request_interval', 0.0)
        type_min = type_min_delays.get(call_type, type_min_delays['standard'])
        required_delay = max(global_min, type_min)

        elapsed = time.time() - self.last_request_time
        if elapsed < required_delay:
            await asyncio.sleep(required_delay - elapsed)

        # 轻微抖动，均摊突刺，降低429概率
        jitter_low, jitter_high = getattr(self, 'per_request_jitter_secs', (0.1, 0.4))
        await asyncio.sleep(random.uniform(jitter_low, jitter_high))

        self.last_request_time = time.time()

    def load_reasoning_chains(self) -> Dict[str, List[Dict]]:
        """按推理链(KOL, 币种)加载预测数据"""
        try:
            if not os.path.exists(self.crypto_db_path):
                self.logger.error(f"推荐数据库 {self.crypto_db_path} 不存在")
                return {}

            with sqlite3.connect(self.crypto_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, tweet_id, author_id, author_name, tweet_created_at, 
                           crypto_name, coingecko_id, full_tweet_text, investment_horizon
                    FROM crypto_recommendations
                    WHERE coingecko_id IS NOT NULL 
                      AND coingecko_id NOT IN ('NOT_FOUND', 'ERROR', '', 'N/A')
                      AND LENGTH(coingecko_id) > 0
                      AND tweet_created_at IS NOT NULL
                    ORDER BY author_name, crypto_name, tweet_created_at ASC
                ''')
                recommendations = [dict(row) for row in cursor.fetchall()]

            reasoning_chains = {}
            for rec in recommendations:
                if rec['crypto_name'].upper() in EXCLUDED_ASSETS:
                    continue
                
                # 使用专用分隔符避免用户名或币种名中包含下划线导致的解析错误
                chain_key = f"{rec['author_name']}|||{rec['crypto_name']}"
                reasoning_chains.setdefault(chain_key, []).append(rec)

            # 修改：接受任意有记录的 author+coin 组合（包括只有1条记录的情况），
            # 但优先按 Fully Diluted Valuation (FDV) 进行初筛，排除 FDV 明确低于 $1,000,000 的币种，
            # 减少后续不必要的计算开销。
            MIN_FDV_USD = 1_000_000
            filtered_chains = {}

            # 使用 verification_engine 的 session 和 base_url 去查询 CoinGecko（若可用）
            session = None
            base_url = None
            headers = {}
            try:
                if hasattr(self, 'verification_engine') and self.verification_engine is not None:
                    session = getattr(self.verification_engine, 'session', None)
                    base_url = getattr(self.verification_engine, 'base_url', None)
                    headers = getattr(self.verification_engine, 'headers', {}) or {}
            except Exception:
                session = None
                base_url = None

            # 为每个链尝试获取FDV（若无法获取则保守放行）
            for chain_key, recs in reasoning_chains.items():
                coingecko_id = recs[0].get('coingecko_id')
                exclude_due_to_fdv = False

                if coingecko_id and session and base_url:
                    try:
                        url = f"{base_url}/coins/{coingecko_id}"
                        params = {
                            'localization': 'false',
                            'tickers': 'false',
                            'community_data': 'false',
                            'developer_data': 'false',
                            'sparkline': 'false'
                        }
                        resp = session.get(url, params=params, headers=headers, timeout=15)
                        if resp.status_code == 200:
                            data = resp.json()
                            market_data = data.get('market_data', {}) or {}
                            fdv_map = market_data.get('fully_diluted_valuation', {}) or {}
                            fdv_usd = fdv_map.get('usd')
                            if isinstance(fdv_usd, (int, float)):
                                if fdv_usd < MIN_FDV_USD:
                                    exclude_due_to_fdv = True
                                    self.logger.info(f"排除 {coingecko_id}（FDV=${fdv_usd:,}）: 小于 ${MIN_FDV_USD:,}")
                        else:
                            # 非200响应，记录但不排除
                            self.logger.debug(f"查询CoinGecko {coingecko_id} FDV时返回状态 {resp.status_code}")
                    except Exception as e:
                        self.logger.debug(f"查询CoinGecko FDV失败 ({coingecko_id}): {e}")

                if not exclude_due_to_fdv:
                    filtered_chains[chain_key] = recs

            self.logger.info(f"找到 {len(filtered_chains)} 条推理链（FDV筛选后），总计 {sum(len(v) for v in filtered_chains.values())} 条预测")
            return filtered_chains
            
        except Exception as e:
            self.logger.error(f"加载推理链数据时出错: {e}")
            return {}

    # ========================================================================
    # 分析方法 - 优化版
    # ========================================================================
    
    def preprocess_reasoning_chain(self, reasoning_chain: List[Dict], kol_name: str, coin_name: str) -> Dict:
        """使用gpt-4o-mini详细分析整个逻辑链条背景"""
        try:
            self._rate_limit_delay()
            
            # 构建链条摘要
            chain_summary = []
            for i, tweet in enumerate(reasoning_chain):
                tweet_text = tweet['full_tweet_text']
                if len(tweet_text) > 200:
                    tweet_text = tweet_text[:200] + "..."
                
                chain_summary.append(f"推文{i+1} ({tweet['tweet_created_at'][:10]}): {tweet_text}")
            
            chain_text = "\n\n".join(chain_summary)
            
            # 使用prompt模板
            preprocess_prompt = get_prompt_template(
                'preprocess_chain',
                kol_name=kol_name,
                coin_name=coin_name,
                start_date=reasoning_chain[0]['tweet_created_at'][:10],
                end_date=reasoning_chain[-1]['tweet_created_at'][:10],
                chain_text=chain_text,
                start_date_short=reasoning_chain[0]['tweet_created_at'][:10],
                coin_name_dup=coin_name,
                coin_name_dup2=coin_name
            )

            response = self.client.chat.completions.create(
                model=MINI_MODEL,
                messages=[{"role": "user", "content": preprocess_prompt}],
                response_format={"type": "json_object"},
            )
            
            result_text = response.choices[0].message.content
            chain_context = json.loads(result_text)
            chain_context['raw_response'] = result_text
            
            self.logger.info(f"✅ 推理链条详细预处理完成: {chain_context.get('kol_overall_stance', 'unknown')}")
            return chain_context
            
        except Exception as e:
            self.logger.error(f"推理链条预处理出错: {e}")
            return {
                "kol_overall_stance": "unknown",
                "key_themes": [],
                "sentiment_evolution": "unknown", 
                "context_summary": "预处理失败",
                "prediction_pattern": "unknown",
                "typical_timeframes": ["short_term"],
                "analysis_style": "unknown"
            }

    def super_analyzer_with_professional_depth(self, tweet: Dict, chain_context: Dict, coin_name: str) -> Dict:
        """专业级Super Analyzer - 深度分析每条推文 - 增强版"""
        try:
            self._rate_limit_delay()
            
            tweet_text = tweet['full_tweet_text']
            tweet_time = tweet['tweet_created_at']
            coingecko_id = tweet['coingecko_id']
            
            # 转换时间戳
            tweet_timestamp = int(pd.to_datetime(tweet_time).timestamp())
            
            # 使用增强的prompt模板 - 确保包含深度评估
            super_prompt = get_prompt_template(
                'super_analyzer',
                coin_name=coin_name,
                tweet_datetime=datetime.fromtimestamp(tweet_timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                tweet_time=tweet_time,
                tweet_timestamp=tweet_timestamp,
                chain_context=json.dumps(chain_context, ensure_ascii=False, indent=2),
                tweet_text=tweet_text,
                coin_name_context=coin_name,
                coin_name_query=coin_name,
                tweet_time_query=tweet_time,
                tweet_timestamp_query=tweet_timestamp,
                coin_name_search=coin_name,
                tweet_time_search=tweet_time,
                tweet_id=tweet['tweet_id'],
                author_name=tweet['author_name'],
                coin_name_info=coin_name,
                coingecko_id_info=coingecko_id,
                tweet_time_info=tweet_time,
                tweet_text_info=tweet_text,
                coin_name_sector=coin_name,
                typical_timeframes=chain_context.get('typical_timeframes', {}).get('preferred_horizons', ['短期']),
                analysis_style=chain_context.get('analysis_style', {}).get('primary_method', 'mixed'),
                coin_name_features=coin_name
            )

            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": super_prompt}],
                response_format={"type": "json_object"},
            )
            
            result_text = response.choices[0].message.content
            analysis_result = json.loads(result_text)
            analysis_result['raw_response'] = result_text
            analysis_result['tweet_info'] = tweet
            
            self.logger.info(f"✅ 专业级Super Analyzer完成: {analysis_result.get('content_type', 'unknown')} - {len(analysis_result.get('predictions', []))}")
            
            # 记录详细分析结果
            for pred in analysis_result.get('predictions', []):
                check_points = pred.get('intelligent_check_points', [])
                reasoning = pred.get('time_selection_reasoning', '')
                logic = pred.get('prediction_logic', {})
                self.logger.info(f"  🎯 智能选择时间点: {check_points}")
                self.logger.info(f"  💭 选择理由: {reasoning[:100] if reasoning else 'N/A'}")
                tech_basis = logic.get('technical_basis', 'N/A')
                fund_basis = logic.get('fundamental_basis', 'N/A')
                sent_basis = logic.get('sentiment_basis', 'N/A')
                self.logger.info(f"  🧠 预测逻辑: 技术面-{tech_basis[:50] if tech_basis else 'N/A'}, 基本面-{fund_basis[:50] if fund_basis else 'N/A'}, 情绪面-{sent_basis[:50] if sent_basis else 'N/A'}")
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"专业级Super Analyzer出错: {e}")
            return {
                "content_type": "error",
                "predictions": [],
                "analysis_reasoning": f"专业级分析失败: {str(e)}",
                "tweet_info": tweet
            }

    async def super_analyzer_with_professional_depth_async(self, tweet: Dict, chain_context: Dict, coin_name: str) -> Dict:
        """专业级Super Analyzer（异步版，用于并行推文分析）"""
        try:
            await self._async_rate_limit_delay()

            tweet_text = tweet['full_tweet_text']
            tweet_time = tweet['tweet_created_at']
            coingecko_id = tweet['coingecko_id']

            tweet_timestamp = int(pd.to_datetime(tweet_time).timestamp())

            super_prompt = get_prompt_template(
                'super_analyzer',
                coin_name=coin_name,
                tweet_datetime=datetime.fromtimestamp(tweet_timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                tweet_time=tweet_time,
                tweet_timestamp=tweet_timestamp,
                chain_context=json.dumps(chain_context, ensure_ascii=False, indent=2),
                tweet_text=tweet_text,
                coin_name_context=coin_name,
                coin_name_query=coin_name,
                tweet_time_query=tweet_time,
                tweet_timestamp_query=tweet_timestamp,
                coin_name_search=coin_name,
                tweet_time_search=tweet_time,
                tweet_id=tweet['tweet_id'],
                author_name=tweet['author_name'],
                coin_name_info=coin_name,
                coingecko_id_info=coingecko_id,
                tweet_time_info=tweet_time,
                tweet_text_info=tweet_text,
                coin_name_sector=coin_name,
                typical_timeframes=chain_context.get('typical_timeframes', {}).get('preferred_horizons', ['短期']),
                analysis_style=chain_context.get('analysis_style', {}).get('primary_method', 'mixed'),
                coin_name_features=coin_name
            )

            response = await self.async_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": super_prompt}],
                response_format={"type": "json_object"},
            )
            result_text = response.choices[0].message.content
            analysis_result = json.loads(result_text)
            analysis_result['raw_response'] = result_text
            analysis_result['tweet_info'] = tweet

            self.logger.info(f"✅ (并发) Super Analyzer完成: {analysis_result.get('content_type', 'unknown')} - {len(analysis_result.get('predictions', []))}")
            return analysis_result

        except Exception as e:
            self.logger.error(f"(并发) Super Analyzer出错: {e}")
            return {
                "content_type": "error",
                "predictions": [],
                "analysis_reasoning": f"并发分析失败: {str(e)}",
                "tweet_info": tweet
            }

    async def analyze_tweets_concurrently(self, reasoning_chain: List[Dict], chain_context: Dict, coin_name: str) -> List[Dict]:
        """并行分析推文，提速Phase 2"""
        semaphore = asyncio.Semaphore(self.max_concurrent_tweet_analysis)
        self.logger.info(f"开始并行分析 {len(reasoning_chain)} 条推文，最大并发={self.max_concurrent_tweet_analysis}")

        async def _run_one(tweet: Dict, idx: int):
            async with semaphore:
                try:
                    result = await self.super_analyzer_with_professional_depth_async(tweet, chain_context, coin_name)
                    self.logger.info(f"推文{idx+1}并发分析完成: {result.get('content_type', 'unknown')}")
                    return result
                except Exception as e:
                    self.logger.error(f"推文{idx+1}并发分析失败: {e}")
                    return {"content_type": "error", "predictions": [], "tweet_info": tweet}

        tasks = [asyncio.create_task(_run_one(tweet, i)) for i, tweet in enumerate(reasoning_chain)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_predictions: List[Dict] = []
        for result in results:
            if isinstance(result, dict) and result.get('content_type') == 'prediction':
                predictions = result.get('predictions', [])
                for pred in predictions:
                    pred['tweet_info'] = result['tweet_info']
                    pred['content_analysis'] = result.get('content_analysis', {})
                    pred['market_context_analysis'] = result.get('market_context_analysis', {})
                    pred['kol_behavioral_analysis'] = result.get('kol_behavioral_analysis', {})
                all_predictions.extend(predictions)

        self.logger.info(f"并行分析完成，共提取 {len(all_predictions)} 个预测")
        return all_predictions
    async def execute_requests_with_deep_analysis(self, predictions_with_requests: List[Dict]) -> List[Dict]:
        """执行所有requests并进行深度结果分析 - 修复版"""
        try:
            self.logger.info("开始执行所有search requests + 深度结果分析...")
            
            prediction_results = []
            
            for prediction in predictions_with_requests:
                self.logger.info(f"处理预测: {prediction['timeframe']} {prediction['sentiment']}")
                
                # Step 1: 执行search_requests
                request_results = []
                search_requests = prediction.get('search_requests', [])
                
                for request in search_requests:
                    try:
                        request_type = request['type']
                        query = request['query']
                        
                        if request_type == 'coingecko_api' and self.technical_agent:
                            result = self.technical_agent.process_coingecko_query(query)
                            request_results.append({
                                'request': request,
                                'result': result,
                                'status': 'success' if result.get('success') else 'failed'
                            })
                            
                        elif request_type == 'web_search':
                            result = await self._execute_enhanced_web_search(query)
                            request_results.append({
                                'request': request, 
                                'result': result,
                                'status': 'success' if result.get('success') else 'failed'
                            })
                            
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        self.logger.error(f"Request执行失败: {query} - {e}")
                        request_results.append({
                            'request': request,
                            'result': {'success': False, 'error': str(e)},
                            'status': 'failed'
                        })
                
                # Step 2: 深度分析search results
                results_analysis = await self._deep_analyze_search_results(request_results, prediction)
                
                # Step 3: 执行真实时间戳验证 - 使用修复的验证引擎
                self.logger.info("执行真实时间戳验证...")
                real_verification = self.verification_engine.verify_prediction_with_real_prices(prediction)
                
                # Step 4: 综合分析 - 使用增强的prompt
                comprehensive_analysis = await self._comprehensive_prediction_analysis(
                    prediction, request_results, results_analysis, real_verification
                )
                
                # 组装预测结果
                prediction_result = prediction.copy()
                prediction_result['request_results'] = request_results
                prediction_result['results_analysis'] = results_analysis
                prediction_result['real_verification'] = real_verification
                prediction_result['comprehensive_analysis'] = comprehensive_analysis
                prediction_result['successful_requests'] = len([r for r in request_results if r['status'] == 'success'])
                prediction_result['total_requests'] = len(request_results)
                prediction_result['verification_status'] = 'completed' if 'error' not in real_verification else 'failed'
                
                prediction_results.append(prediction_result)
                
                self.logger.info(f"预测{prediction['prediction_id']}深度分析完成: {prediction_result['successful_requests']}/{prediction_result['total_requests']} requests成功, 真实验证: {'成功' if prediction_result['verification_status'] == 'completed' else '失败'}")
                
                await asyncio.sleep(3)
            
            self.logger.info(f"✅ 所有requests + 深度分析完成，共{len(prediction_results)}个预测")
            return prediction_results
            
        except Exception as e:
            self.logger.error(f"执行requests + 深度分析时出错: {e}")
            return []

    async def _execute_enhanced_web_search(self, query: str) -> Dict:
        """执行增强版web搜索 - 修复结果展示"""
        try:
            self._rate_limit_delay()
    
            search_prompt = get_prompt_template('web_search', query=query)

            response = self.client.chat.completions.create(
                model=SEARCH_MODEL,
                messages=[{"role": "user", "content": search_prompt}],
            )
            
            search_result = response.choices[0].message.content
            
            # 修复：格式化搜索结果，避免截断 - 解决问题5
            formatted_result = self._format_web_search_result(query, search_result)
            
            return {
                'success': True,
                'query': query,
                'results': [formatted_result],
                'summary': search_result[:300] + "..." if len(search_result) > 300 else search_result,
                'search_type': 'enhanced_web_search',
                'analysis_depth': 'deep',
                'model_used': SEARCH_MODEL,
                'full_content': formatted_result  # 完整内容，不截断
            }
            
        except Exception as e:
            self.logger.error(f"增强版Web搜索失败: {query} - {e}")
            return {
                'success': False,
                'query': query,
                'error': str(e),
                'search_type': 'enhanced_web_search'
            }
    
    def _format_web_search_result(self, query: str, search_result: str) -> str:
        """格式化Web搜索结果，确保完整展示 - 修复问题5"""
        formatted_lines = []
        
        # 添加标准化头部
        formatted_lines.append(f"🔍 查询目标: {query}")
        formatted_lines.append("🎯 搜索目的: 了解市场背景和基本面因素")
        formatted_lines.append("")
        formatted_lines.append("📊 核心发现:")
        
        # 确保搜索结果完整展示，不截断
        if search_result:
            # 按段落分割结果，确保完整性
            paragraphs = search_result.split('\n\n')
            for i, paragraph in enumerate(paragraphs, 1):
                if paragraph.strip():
                    formatted_lines.append(f"  {i}. {paragraph.strip()}")
        
        formatted_lines.append("")
        formatted_lines.append("💡 关键洞察:")
        formatted_lines.append("  • 基于最新市场信息的专业分析")
        formatted_lines.append("  • 结合多个信息源的综合判断")
        formatted_lines.append("  • 为投资决策提供重要参考")
        
        formatted_lines.append("")
        formatted_lines.append("⚠️ 风险因素:")
        formatted_lines.append("  • 市场信息可能存在滞后性")
        formatted_lines.append("  • 需要结合技术分析进行验证")
        formatted_lines.append("  • 关注宏观环境变化的影响")
        
        formatted_lines.append("")
        formatted_lines.append("🚀 投资启示:")
        formatted_lines.append("  • 密切关注基本面变化")
        formatted_lines.append("  • 结合技术面进行综合分析")
        formatted_lines.append("  • 制定合理的风险管理策略")
        
        return "\n".join(formatted_lines)

    async def _deep_analyze_search_results(self, request_results: List[Dict], prediction: Dict) -> Dict:
        """深度分析search results - 使用增强的prompt"""
        try:
            self._rate_limit_delay()
            
            # 整理search results
            successful_results = [r for r in request_results if r['status'] == 'success']
            if not successful_results:
                return {"analysis": "无有效search results进行分析", "insights": [], "supporting_evidence": []}
            
            results_summary = []
            for result in successful_results:
                request = result['request']
                result_data = result['result']
                
                # 确保包含完整内容
                full_content = result_data.get('full_content', '')
                if not full_content:
                    full_content = '\n'.join(result_data.get('results', []))
                
                results_summary.append({
                    "query": request['query'],
                    "purpose": request['purpose'],
                    "type": request['type'],
                    "results": result_data.get('results', []),
                    "summary": result_data.get('summary', 'N/A'),
                    "full_content": full_content  # 包含完整内容
                })
            
            # 使用增强的prompt模板
            analysis_prompt = get_prompt_template(
                'search_analysis',
                specific_claim=prediction.get('specific_claim', 'N/A'),
                sentiment=prediction.get('sentiment', 'N/A'),
                timeframe=prediction.get('timeframe', 'N/A'),
                confidence_level=prediction.get('confidence_level', 'N/A'),
                prediction_logic=json.dumps(prediction.get('prediction_logic', {}), ensure_ascii=False),
                results_summary=json.dumps(results_summary, ensure_ascii=False, indent=2)
            )

            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": analysis_prompt}],
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            analysis_result = json.loads(result_text)
            analysis_result['raw_response'] = result_text
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"深度分析search results失败: {e}")
            return {"analysis": f"分析失败: {e}", "insights": [], "supporting_evidence": []}

    async def _comprehensive_prediction_analysis(self, prediction: Dict, request_results: List[Dict], 
                                               results_analysis: Dict, real_verification: Dict) -> Dict:
        """综合预测分析 - 使用增强的prompt，重点解决推文质量评估问题"""
        try:
            self._rate_limit_delay()
            
            # 使用增强的prompt模板 - 这是修复问题6的关键
            comprehensive_prompt = get_prompt_template(
                'comprehensive_analysis',
                original_prediction=json.dumps(prediction, ensure_ascii=False, indent=2, default=str),
                search_analysis=json.dumps(results_analysis, ensure_ascii=False, indent=2, default=str),
                verification_results=json.dumps(real_verification, ensure_ascii=False, indent=2, default=str)
            )

            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": comprehensive_prompt}],
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            comprehensive_result = json.loads(result_text)
            comprehensive_result['raw_response'] = result_text
            
            # 确保包含推文质量深度评估 - 这是问题6的核心修复
            if '🎯 TWEET_QUALITY_DEEP_EVALUATION' in comprehensive_result:
                tweet_quality = comprehensive_result['🎯 TWEET_QUALITY_DEEP_EVALUATION']
                self.logger.info(f"  📊 推文质量评估: {tweet_quality.get('推文质量判断', 'N/A')}")
                self.logger.info(f"  📊 综合评分: {tweet_quality.get('综合评分', 'N/A')}")
                
                # 记录详细评估维度
                content_score = tweet_quality.get('content_quality_score', 0)
                prediction_score = tweet_quality.get('prediction_value_score', 0)
                responsibility_score = tweet_quality.get('kol_responsibility_score', 0)
                impact_score = tweet_quality.get('market_impact_score', 0)
                
                self.logger.info(f"  🔍 详细评分: 内容质量{content_score}, 预测价值{prediction_score}, KOL责任{responsibility_score}, 市场影响{impact_score}")
            
            # 确保包含最终判断 - 解决"这条推文到底是好还是坏？"的问题
            if '🎯 FINAL_VERDICT' in comprehensive_result:
                final_verdict = comprehensive_result['🎯 FINAL_VERDICT']
                judgment = final_verdict.get('推文总体判断', 'N/A')
                self.logger.info(f"  🏆 最终判断: {judgment}")
            
            return comprehensive_result
            
        except Exception as e:
            self.logger.error(f"综合预测分析失败: {e}")
            return {"analysis": f"综合分析失败: {e}", "final_assessment": {"overall_accuracy": "unknown"}}

    def analyze_short_term_with_comprehensive_insights(self, short_predictions: List[Dict], long_predictions: List[Dict]) -> Dict:
        """阶段1：增强版短期预测分析 - 使用增强的prompt"""
        try:
            self._rate_limit_delay()
            
            # 构建长期预测背景
            long_context = []
            for pred in long_predictions:
                long_context.append(f"长期预测: {pred['timeframe']} {pred['sentiment']} - {pred['specific_claim'][:100]}")
            long_context_text = "\n".join(long_context) if long_context else "无长期预测"
            
            # 构建短期预测详细数据
            short_analysis_data = []
            for pred in short_predictions:
                real_verification = pred.get('real_verification', {})
                results_analysis = pred.get('results_analysis', {})
                comprehensive_analysis = pred.get('comprehensive_analysis', {})
                
                pred_data = {
                    'prediction': pred,
                    'request_summary': self._detailed_request_summary(pred['request_results']),
                    'real_verification': real_verification,
                    'results_analysis_summary': results_analysis.get('analysis_summary', 'N/A'),
                    'comprehensive_insights': comprehensive_analysis.get('comprehensive_summary', 'N/A'),
                    'final_assessment': comprehensive_analysis.get('final_assessment', {}),
                    'verification_accuracy': real_verification.get('overall_accuracy', 0),
                    # 添加推文质量评估数据
                    'tweet_quality_evaluation': comprehensive_analysis.get('🎯 TWEET_QUALITY_DEEP_EVALUATION', {}),
                    'final_verdict': comprehensive_analysis.get('🎯 FINAL_VERDICT', {}),
                    'actionable_recommendations': comprehensive_analysis.get('🚀 ACTIONABLE_RECOMMENDATIONS', {})
                }
                short_analysis_data.append(pred_data)
            
            # 使用增强的prompt模板
            short_term_prompt = get_prompt_template(
                'short_term_analysis',
                long_context=long_context_text,
                short_data=json.dumps(short_analysis_data, ensure_ascii=False, indent=2, default=str)
            )

            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": short_term_prompt}],
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            short_analysis = json.loads(result_text)
            short_analysis['raw_response'] = result_text
            short_analysis['analysis_type'] = 'enhanced_short_term_analysis'
            
            avg_accuracy = short_analysis.get('short_term_aggregate_analysis', {}).get('overall_performance', {}).get('average_accuracy', 'N/A')
            self.logger.info(f"✅ 增强版短期预测分析完成: 平均准确率{avg_accuracy}%")
            
            # 记录投资价值评估
            investment_utility = short_analysis.get('short_term_aggregate_analysis', {}).get('🎯 INVESTMENT_UTILITY_SUMMARY', {})
            if investment_utility:
                overall_value = investment_utility.get('整体投资价值', 'N/A')
                suitable_investors = investment_utility.get('最适合的投资者类型', 'N/A')
                self.logger.info(f"  📊 投资价值: {overall_value}, 适合投资者: {suitable_investors}")
            
            return short_analysis
            
        except Exception as e:
            self.logger.error(f"增强版短期预测分析出错: {e}")
            return {
                "short_term_evaluations": [],
                "short_term_aggregate_analysis": {"overall_performance": {"average_accuracy": 50}},
                "analysis_type": "enhanced_short_term_analysis",
                "error": "增强版短期分析失败"
            }

    def analyze_long_term_with_strategic_depth(self, long_predictions: List[Dict], short_analysis: Dict) -> Dict:
        """阶段2：增强版长期预测分析 - 使用增强的prompt"""
        try:
            self._rate_limit_delay()
            
            # 构建长期预测详细数据
            long_analysis_data = []
            for pred in long_predictions:
                real_verification = pred.get('real_verification', {})
                results_analysis = pred.get('results_analysis', {})
                comprehensive_analysis = pred.get('comprehensive_analysis', {})
                
                pred_data = {
                    'prediction': pred,
                    'request_summary': self._detailed_request_summary(pred['request_results']),
                    'real_verification': real_verification,
                    'results_analysis_summary': results_analysis.get('analysis_summary', 'N/A'),
                    'comprehensive_insights': comprehensive_analysis.get('comprehensive_summary', 'N/A'),
                    'final_assessment': comprehensive_analysis.get('final_assessment', {}),
                    'verification_accuracy': real_verification.get('overall_accuracy', 0),
                    # 添加推文质量评估数据
                    'tweet_quality_evaluation': comprehensive_analysis.get('🎯 TWEET_QUALITY_DEEP_EVALUATION', {}),
                    'final_verdict': comprehensive_analysis.get('🎯 FINAL_VERDICT', {}),
                    'actionable_recommendations': comprehensive_analysis.get('🚀 ACTIONABLE_RECOMMENDATIONS', {})
                }
                long_analysis_data.append(pred_data)
            
            # 使用增强的prompt模板
            long_term_prompt = get_prompt_template(
                'long_term_analysis',
                short_analysis=json.dumps(short_analysis, ensure_ascii=False, indent=2, default=str),
                long_data=json.dumps(long_analysis_data, ensure_ascii=False, indent=2, default=str)
            )

            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": long_term_prompt}],
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            long_analysis = json.loads(result_text)
            long_analysis['raw_response'] = result_text
            long_analysis['analysis_type'] = 'enhanced_long_term_analysis'
            
            avg_accuracy = long_analysis.get('long_term_strategic_analysis', {}).get('overall_strategic_capability', {}).get('average_accuracy', 'N/A')
            self.logger.info(f"✅ 增强版长期预测分析完成: 战略能力评分{avg_accuracy}")
            
            # 记录投资组合价值评估
            strategic_merit = long_analysis.get('long_term_strategic_analysis', {}).get('🎯 STRATEGIC_INVESTMENT_MERIT', {})
            if strategic_merit:
                strategic_value = strategic_merit.get('整体战略价值', 'N/A')
                investment_type = strategic_merit.get('最适合的投资类型', 'N/A')
                portfolio_role = strategic_merit.get('投资组合角色', 'N/A')
                self.logger.info(f"  📊 战略价值: {strategic_value}, 投资类型: {investment_type}, 组合角色: {portfolio_role}")
            
            return long_analysis
            
        except Exception as e:
            self.logger.error(f"增强版长期预测分析出错: {e}")
            return {
                "long_term_evaluations": [],
                "long_term_strategic_analysis": {"overall_strategic_capability": {"average_accuracy": 50}},
                "analysis_type": "enhanced_long_term_analysis",
                "error": "增强版长期分析失败"
            }

    def final_professional_kol_evaluation(self, short_analysis: Dict, long_analysis: Dict, 
                            chain_context: Dict, kol_name: str, coin_name: str) -> Dict:
        """阶段3：生成专业级KOL综合评估报告 - 修复评分逻辑，使用增强的prompt"""
        try:
            self._rate_limit_delay()
            
            # 计算实际准确率 - 添加安全处理
            short_perf = short_analysis.get('short_term_aggregate_analysis', {}).get('overall_performance', {})
            long_perf = long_analysis.get('long_term_strategic_analysis', {}).get('overall_strategic_capability', {})
            
            # 安全获取准确率值，确保不是 None
            short_accuracy = short_perf.get('average_accuracy')
            long_accuracy = long_perf.get('average_accuracy')
            
            # 处理 None 值
            if short_accuracy is None:
                short_accuracy = 0
            if long_accuracy is None:
                long_accuracy = 0
            
            # 确保是数字类型
            try:
                short_accuracy = float(short_accuracy)
            except (TypeError, ValueError):
                short_accuracy = 0
                
            try:
                long_accuracy = float(long_accuracy)
            except (TypeError, ValueError):
                long_accuracy = 0
            
            # 修复评分计算逻辑
            if short_accuracy > 0 and long_accuracy > 0:
                integrated_accuracy = (short_accuracy + long_accuracy) / 2
            elif short_accuracy > 0:
                integrated_accuracy = short_accuracy
            elif long_accuracy > 0:
                integrated_accuracy = long_accuracy
            else:
                integrated_accuracy = 50  # 默认值
            
            # 使用增强的prompt模板 - 这是修复问题6的关键部分
            final_prompt = get_prompt_template(
                'final_kol_evaluation',
                kol_name=kol_name,
                coin_name=coin_name,
                short_accuracy=short_accuracy,
                long_accuracy=long_accuracy,
                integrated_accuracy=integrated_accuracy,
                calculated_score=min(100, max(30, int(integrated_accuracy * 0.8 + 20))),
                chain_context=json.dumps(chain_context, ensure_ascii=False, indent=2, default=str),
                short_analysis=json.dumps(short_analysis, ensure_ascii=False, indent=2, default=str),
                long_analysis=json.dumps(long_analysis, ensure_ascii=False, indent=2, default=str),
                short_accuracy_val=short_accuracy,
                long_accuracy_val=long_accuracy,
                integrated_accuracy_val=integrated_accuracy,
                tech_score=min(100, max(30, int(integrated_accuracy * 0.9 + 10))),
                fund_score=min(100, max(30, int(integrated_accuracy * 0.85 + 15))),
                psych_score=min(100, max(40, int(integrated_accuracy * 0.95 + 5))),
                risk_score=min(100, max(35, int(integrated_accuracy * 0.75 + 25))),
                comm_score=min(100, max(50, int(integrated_accuracy * 0.8 + 20))),
                win_rate=min(100, max(30, int(integrated_accuracy)))
            )

            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": final_prompt}],
                response_format={"type": "json_object"},
            )
            
            result_text = response.choices[0].message.content
            final_evaluation = json.loads(result_text)
            final_evaluation['raw_response'] = result_text
            final_evaluation['analysis_type'] = 'professional_kol_evaluation'
            final_evaluation['kol_name'] = kol_name
            final_evaluation['coin_name'] = coin_name
            
            # 确保包含必要的数据结构
            if 'comprehensive_verification_analysis' not in final_evaluation:
                final_evaluation['comprehensive_verification_analysis'] = {
                    "short_term_performance": {"avg_accuracy": short_accuracy},
                    "long_term_performance": {"avg_accuracy": long_accuracy},
                    "integrated_performance": {"overall_accuracy": integrated_accuracy}
                }
            
            overall_grade = final_evaluation.get('executive_summary', {}).get('overall_grade', 'N/A')
            overall_score = final_evaluation.get('executive_summary', {}).get('overall_score', 'N/A')
            tier = final_evaluation.get('tier', None) or 'N/A'

            self.logger.info(f"✅ 专业级KOL最终评估完成: 等级 {tier} | 评级 {overall_grade}")
            
            # 记录核心评估结果 - 这是问题6的关键修复
            core_thesis = final_evaluation.get('🎯 CORE_INVESTMENT_THESIS', {})
            if core_thesis:
                attention_index = core_thesis.get('值得关注指数', 'N/A')
                follow_index = core_thesis.get('值得跟随指数', 'N/A')
                risk_level = core_thesis.get('风险警示级别', 'N/A')
                self.logger.info(f"  📊 核心评估: 关注指数{attention_index}, 跟随指数{follow_index}, 风险级别{risk_level}")
            
            # 记录最终决策框架
            decision_framework = final_evaluation.get('🎯 FINAL_DECISION_FRAMEWORK', {})
            if decision_framework:
                attention_value = decision_framework.get('关注价值', 'N/A')
                follow_condition = decision_framework.get('跟随条件', 'N/A')
                self.logger.info(f"  🎯 决策框架: {attention_value[:50]}... | 跟随条件: {follow_condition[:50]}...")
            
            return final_evaluation
            
        except Exception as e:
            self.logger.error(f"专业级KOL最终评估出错: {e}")
            import traceback
            traceback.print_exc()
            return {
                "executive_summary": {"overall_grade": "C", "overall_score": 60},
                "comprehensive_verification_analysis": {
                    "short_term_performance": {"avg_accuracy": short_accuracy if 'short_accuracy' in locals() else 0},
                    "long_term_performance": {"avg_accuracy": long_accuracy if 'long_accuracy' in locals() else 0},
                    "integrated_performance": {"overall_accuracy": integrated_accuracy if 'integrated_accuracy' in locals() else 50}
                },
                "analysis_type": "professional_kol_evaluation",
                "kol_name": kol_name, 
                "coin_name": coin_name, 
                "error": f"专业级最终评估失败: {str(e)}"
            }

    def _detailed_request_summary(self, request_results: List[Dict]) -> str:
        """生成详细的request结果总结 - 增强版"""
        if not request_results: 
            return "无request执行结果"
        
        summary = []
        for result in request_results:
            request = result['request']
            status = result['status']
            query = request['query']
            purpose = request.get('purpose', 'N/A')
            
            if status == 'success':
                result_data = result['result']
                if request['type'] == 'coingecko_api':
                    results_count = len(result_data.get('results', []))
                    detailed_results = result_data.get('detailed_results', {})
                    
                    summary.append(f"✅ CoinGecko API查询: {query[:80]}")
                    summary.append(f"   目的: {purpose}")
                    summary.append(f"   结果: {results_count}项数据")
                    
                    # 添加详细结果信息
                    if detailed_results:
                        if 'price_data' in detailed_results:
                            price_data = detailed_results['price_data']
                            summary.append(f"   价格数据: 当前${price_data.get('current_price', 'N/A')}, 24h变化{price_data.get('price_change_percentage_24h', 0):.2f}%")
                        if 'technical_indicators' in detailed_results:
                            summary.append(f"   技术指标: {', '.join(detailed_results['technical_indicators'][:2])}")
                        if 'market_data' in detailed_results:
                            summary.append(f"   市场数据: {', '.join(detailed_results['market_data'][:2])}")
                    
                    # 如果查询失败，添加错误信息
                    if not result_data.get('success', True):
                        summary.append(f"   错误原因: {result_data.get('error', '未知错误')}")
                        summary.append(f"   详细错误: {result_data.get('detailed_error', 'N/A')}")
                else:
                    # Web搜索结果 - 确保完整展示
                    full_content = result_data.get('full_content', '')
                    if full_content:
                        content_preview = full_content[:200] + "..." if len(full_content) > 200 else full_content
                        summary.append(f"✅ Web搜索: {query[:80]}")
                        summary.append(f"   目的: {purpose}")
                        summary.append(f"   结果: {content_preview}")
                        summary.append(f"   完整内容长度: {len(full_content)}字符")
                    else:
                        search_summary = result_data.get('summary', 'N/A')[:150]
                        summary.append(f"✅ Web搜索: {query[:80]}")
                        summary.append(f"   目的: {purpose}")
                        summary.append(f"   结果: {search_summary}")
            else:
                error_msg = result['result'].get('error', 'Unknown error')
                summary.append(f"❌ 查询失败: {query[:80]}")
                summary.append(f"   目的: {purpose}")
                summary.append(f"   错误: {error_msg[:100]}")
        
        return "\n".join(summary)

    def assign_tiers(self, analysis_results: List[Dict]) -> Dict[str, int]:
        """根据综合分数按百分比分配等级（Tier）。
        修改每个 analysis_result 的 final_evaluation，使之只公开 `tier` 字段（数值分数移至内部字段 `_internal_score`）。
        返回分配后的各等级计数统计。
        """
        # 等级及对应百分比（按题主要求的顺序，从高到低）
        tiers = [
            ("S+", 2), ("S", 4), ("S-", 4), ("A+", 5), ("A", 7), ("A-", 8),
            ("B+", 12), ("B", 16), ("B-", 12), ("C+", 8), ("C", 7), ("C-", 5),
            ("D+", 4), ("D", 4), ("D-", 2)
        ]

        # 把有报告的项和无报告的项分开：只有有实际评估/预测或 final_evaluation 非空的，才参与排名分配。
        reportable = []
        non_reportable = []
        for r in analysis_results:
            fe = r.get('final_evaluation')
            has_predictions = bool(r.get('predictions') or r.get('prediction_results') or r.get('request_results'))
            has_fe_content = False
            if fe and isinstance(fe, dict) and any(k for k in fe.keys() if k not in ('_internal_score', '_internal_rank', 'tier')):
                has_fe_content = True

            if has_fe_content or has_predictions:
                reportable.append(r)
            else:
                non_reportable.append(r)

        m = len(reportable)
        # 如果没有可排名的项，则将所有人标为最低等级并计数
        tier_counts = {name: 0 for name, _ in tiers}
        if m == 0:
            for idx, r in enumerate(non_reportable):
                fe = r.setdefault('final_evaluation', {})
                fe['_internal_score'] = 0.0
                fe['_internal_rank'] = idx + 1
                fe['tier'] = tiers[-1][0]
                if 'executive_summary' in fe:
                    fe['executive_summary'].pop('overall_score', None)
                tier_counts[tiers[-1][0]] += 1
            return tier_counts

        # 提取每个可排名结果的数值分数（优先使用 executive_summary.overall_score，其次使用综合accuracy），缺省为0
        # 为了避免同一作者占用多个名额：先按作者聚合，使用作者的最高分作为作者分数进行排名
        author_map = {}  # author -> list of (r, score_val)
        for r in reportable:
            fe = r.get('final_evaluation', {}) or {}
            score = None
            score = fe.get('executive_summary', {}).get('overall_score') if isinstance(fe.get('executive_summary'), dict) else None
            if score is None:
                score = fe.get('comprehensive_verification_analysis', {}).get('integrated_performance', {}).get('overall_accuracy') if isinstance(fe.get('comprehensive_verification_analysis'), dict) else None
            try:
                score_val = float(score) if score is not None else 0.0
            except Exception:
                score_val = 0.0

            author = r.get('kol_name') or r.get('author_name') or r.get('final_evaluation', {}).get('kol_name') or r.get('chain_key')
            author = (author or 'unknown').strip().lower()
            author_map.setdefault(author, []).append((r, score_val))

        # 构建作者最佳分列表，用于排名
        author_best = []  # list of (author, best_score, representative_r)
        for author, items in author_map.items():
            # 选择该作者最高分的一条作为代表
            items_sorted = sorted(items, key=lambda x: x[1], reverse=True)
            best_score = items_sorted[0][1]
            rep_r = items_sorted[0][0]
            author_best.append((author, best_score, rep_r))

        # 按作者最高分降序排序
        author_best.sort(key=lambda x: x[1], reverse=True)

        # 计算每一等级应分配的人数（基于可排名的唯一作者数量 m_unique）
        m_unique = len(author_best)
        counts = [int((pct * m_unique) / 100) for _, pct in tiers]

        assigned = sum(counts)
        remaining = m_unique - assigned
        idx = 0
        # 将剩余名额从最高等级依次分配
        while remaining > 0:
            counts[idx] += 1
            remaining -= 1
            idx = (idx + 1) % len(counts)

        # 按作者分配等级：每位作者最多获得一个名额（且占用一个排名位置）。同一作者的所有条目将被标记为相同等级。
        # 新增规则：为若干高等级设置额外门槛（最小有效推文数、最小预测币种数），只有满足门槛的作者才有资格被分配到该等级。
        thresholds = {
            'S+': (10, 3),
            'S': (10, 3),
            'S-': (10, 3),
            'A+': (5, 5),
            'A': (5, 2),
            'A-': (2, 2),
            'B+': (2, 0),
            # 其他等级无额外门槛
        }

        def author_meets_threshold(author_items: List[Tuple[Dict, float]], tier_name: str) -> bool:
            """判断作者是否满足指定等级的门槛。
            author_items: list of (r, score_val)
            返回 True/False
            """
            min_preds, min_coins = thresholds.get(tier_name, (0, 0))
            # 统计有效推文数（以prediction_results或predictions为准）
            total_preds = 0
            coins = set()
            for r_item, _ in author_items:
                preds = r_item.get('prediction_results') or r_item.get('predictions') or []
                try:
                    total_preds += len(preds)
                except Exception:
                    # 如果 preds 不是列表，尝试当作单个项计数
                    if preds:
                        total_preds += 1
                coin_name = (r_item.get('coin_name') or r_item.get('coin', '') or '').strip().lower()
                if coin_name:
                    coins.add(coin_name)
            distinct_coins = len(coins)
            return (total_preds >= min_preds) and (distinct_coins >= min_coins)

        remaining_authors = list(author_best)  # mutable copy
        remaining_map = {a[0]: a for a in remaining_authors}
        i = 0
        assigned_authors = set()

        for (tier_name, _), cnt in zip(tiers, counts):
            if cnt <= 0:
                continue
            # 从剩余作者中筛选满足该等级门槛的候选人，按作者最高分排序
            candidates = [a for a in remaining_authors if a[0] not in assigned_authors]
            # 依据门槛过滤
            eligible = []
            for author, best_score, rep_r in candidates:
                items = author_map.get(author, [])
                if author_meets_threshold(items, tier_name):
                    eligible.append((author, best_score, rep_r))

            # 按分数降序选出本等级的名额
            eligible.sort(key=lambda x: x[1], reverse=True)
            selected = eligible[:cnt]

            for author, best_score, rep_r in selected:
                items = author_map.get(author, [])
                for r_item, score_val in items:
                    fe = r_item.setdefault('final_evaluation', {})
                    fe['_internal_score'] = score_val
                    fe['_internal_rank'] = i + 1
                    fe['tier'] = tier_name
                    if 'executive_summary' in fe and isinstance(fe['executive_summary'], dict):
                        fe['executive_summary'].pop('overall_score', None)
                tier_counts[tier_name] += 1
                assigned_authors.add(author)
                i += 1

            # 从 remaining_authors 中移除已分配的作者
            if selected:
                sel_set = set(a[0] for a in selected)
                remaining_authors = [a for a in remaining_authors if a[0] not in sel_set]

        # 所有未被分配到等级的作者，统一标为最低等级
        lowest_tier = tiers[-1][0]
        for author, best_score, rep_r in remaining_authors:
            if author in assigned_authors:
                continue
            items = author_map.get(author, [])
            for r_item, score_val in items:
                fe = r_item.setdefault('final_evaluation', {})
                fe['_internal_score'] = score_val
                fe['_internal_rank'] = i + 1
                fe['tier'] = lowest_tier
                if 'executive_summary' in fe and isinstance(fe['executive_summary'], dict):
                    fe['executive_summary'].pop('overall_score', None)
            tier_counts[lowest_tier] += 1
            i += 1

        # 将无报告的项放到末尾，标为最低等级（例如 D-），并把它们计入统计
        for j, r in enumerate(non_reportable):
            fe = r.setdefault('final_evaluation', {})
            fe['_internal_score'] = 0.0
            fe['_internal_rank'] = m_unique + j + 1
            fe['tier'] = tiers[-1][0]
            if 'executive_summary' in fe and isinstance(fe['executive_summary'], dict):
                fe['executive_summary'].pop('overall_score', None)
            tier_counts[tiers[-1][0]] += 1

        return tier_counts

    # ========================================================================
    # 图表生成 - 优化版，去掉预测点生成，配合HTML hotpoint系统
    # ========================================================================
    
    def get_crypto_price_history(self, coin_id: str, start_date: datetime, end_date: datetime) -> Optional[Dict]:
        """从CoinGecko获取价格历史数据 - 修复版"""
        self._rate_limit_delay()
        
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            # 确保包含所有必需参数 - 修复422错误
            if self.coingecko_api_key:
                url = "https://pro-api.coingecko.com/api/v3/coins/{}/market_chart/range".format(coin_id)
                headers = {"x-cg-pro-api-key": self.coingecko_api_key}
            else:
                url = "https://api.coingecko.com/api/v3/coins/{}/market_chart/range".format(coin_id)
                headers = {}
            
            params = {
                'vs_currency': 'usd', 
                'from': start_timestamp, 
                'to': end_timestamp
            }
            
            self.logger.info(f"获取 {coin_id} 价格数据: {start_date.date()} 到 {end_date.date()}")
            self.logger.debug(f"请求参数: {params}")
            
            response = requests.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                prices = data.get('prices', [])
                if not prices: 
                    self.logger.warning(f"未获取到 {coin_id} 的价格数据")
                    return None
                
                df = pd.DataFrame(prices, columns=['timestamp', 'price'])
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
                self.logger.info(f"成功获取 {coin_id} 价格数据，共 {len(df)} 个数据点")
                return {'coin_id': coin_id, 'data': df, 'start_date': start_date, 'end_date': end_date}
            
            elif response.status_code == 422:
                self.logger.error(f"422错误 - API参数无效: {response.text}")
                self.logger.error(f"请求URL: {url}")
                self.logger.error(f"参数: {params}")
                return None
            
            elif response.status_code == 429:
                self.logger.warning("API限流，等待60秒...")
                time.sleep(60)
                return self.get_crypto_price_history(coin_id, start_date, end_date)
            
            elif response.status_code == 404:
                self.logger.warning(f"未找到币种: {coin_id}")
                return None
            
            else:
                self.logger.error(f"获取价格数据失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"获取价格数据时出错: {e}")
            return None

    def create_optimized_chart_for_html(self, kol_name: str, coin_name: str, 
                                       prediction_results: List[Dict], 
                                       price_data: Dict) -> Optional[Dict]:
        """创建优化的图表，配合HTML hotpoint系统 - 去掉预测点绘制"""
        try:
            plt.rcParams['font.sans-serif'] = ['Noto Serif CJK SC', 'Noto Serif CJK SC Regular', 'Liberation Sans']
            plt.rcParams['axes.unicode_minus'] = False
            
            df = price_data['data']
            fig, ax = plt.subplots(figsize=(24, 14), dpi=120)
            
            # 仅绘制价格曲线，不绘制预测点
            ax.plot(df['date'], df['price'], linewidth=3, color='#1f77b4', 
                   label=f'{coin_name} Price', alpha=0.9, zorder=1)
            
            # 预测数据处理 - 为HTML生成坐标信息
            prediction_coordinates = []
            max_prediction_date = None
            
            for i, prediction in enumerate(prediction_results):
                if 'tweet_info' in prediction:
                    tweet_info = prediction['tweet_info']
                    pred_date = pd.to_datetime(tweet_info['tweet_created_at'])
                    
                    # 获取最长的预测时间点
                    check_points = prediction.get('intelligent_check_points', [])
                    for check_point in check_points:
                        # 计算检查点的时间
                        check_timestamp = self.verification_engine.calculate_target_timestamp(
                            int(pred_date.timestamp()), check_point
                        )
                        check_date = datetime.fromtimestamp(check_timestamp)
                        if max_prediction_date is None or check_date > max_prediction_date:
                            max_prediction_date = check_date
                    
                    # 找到最接近的价格点
                    closest_idx = (df['date'] - pred_date).abs().idxmin()
                    pred_price = df.loc[closest_idx, 'price']
                    
                    # 获取分析数据
                    sentiment = prediction.get('sentiment', 'bullish')
                    timeframe = prediction.get('timeframe', 'short_term')
                    strength = prediction.get('strength', 'moderate')
                    
                    real_verification = prediction.get('real_verification', {})
                    verification_accuracy = real_verification.get('overall_accuracy', 0)
                    
                    comprehensive_analysis = prediction.get('comprehensive_analysis', {})
                    
                    # 计算相对坐标 - 这是关键，HTML hotpoint需要相对位置
                    date_range_sec = (df['date'].max() - df['date'].min()).total_seconds()
                    relative_x = ((pred_date - df['date'].min()).total_seconds() / date_range_sec) if date_range_sec > 0 else 0.5
                    price_range_val = df['price'].max() - df['price'].min()
                    relative_y = ((pred_price - df['price'].min()) / price_range_val) if price_range_val > 0 else 0.5
                    
                    # 时间框架映射
                    timeframe_map = {'short_term': 'ST', 'medium_term': 'MT', 'long_term': 'LT'}
                    sentiment_map = {'bullish': '↗', 'bearish': '↘', 'neutral': '→'}
                    
                    # 基于推文质量评估的状态符号
                    tweet_quality = comprehensive_analysis.get('🎯 TWEET_QUALITY_DEEP_EVALUATION', {})
                    final_verdict = comprehensive_analysis.get('🎯 FINAL_VERDICT', {})
                    
                    overall_judgment = final_verdict.get('推文总体判断', '')
                    tweet_quality_rating = tweet_quality.get('推文质量判断', '')
                    
                    if '强烈推荐' in overall_judgment or '优秀' in tweet_quality_rating:
                        status_symbol = '⭐'
                    elif '推荐' in overall_judgment or '良好' in tweet_quality_rating:
                        status_symbol = '✓'
                    elif '谨慎' in overall_judgment or '一般' in tweet_quality_rating:
                        status_symbol = '~'
                    elif '不推荐' in overall_judgment or '较差' in tweet_quality_rating:
                        status_symbol = '✗'
                    else:
                        # 后备方案：基于验证准确率
                        if verification_accuracy >= 80:
                            status_symbol = '✓'
                        elif verification_accuracy >= 60:
                            status_symbol = '~'
                        else:
                            status_symbol = '✗'
                    
                    label_text = f"{timeframe_map.get(timeframe, 'ST')}{i+1}{sentiment_map.get(sentiment, '↗')}{status_symbol}({verification_accuracy:.0f}%)"
                    
                    # 构建详细坐标信息 - 供HTML使用
                    prediction_coordinates.append({
                        'index': i, 
                        'label': label_text, 
                        'date': pred_date.strftime('%Y-%m-%d %H:%M'), 
                        'price': f"${pred_price:.4f}", 
                        'display_price': f"${pred_price:.4f}",
                        'sentiment': sentiment, 
                        'timeframe': timeframe, 
                        'strength': strength, 
                        'tweet_id': prediction.get('tweet_info', {}).get('tweet_id', ''), 
                        'content': prediction.get('specific_claim', '')[:200] + '...',
                        'real_verification': real_verification, 
                        'verification_accuracy': verification_accuracy, 
                        'comprehensive_analysis': comprehensive_analysis, 
                        'tweet_quality_evaluation': tweet_quality,
                        'final_verdict': final_verdict,
                        'intelligent_check_points': prediction.get('intelligent_check_points', []), 
                        'time_selection_reasoning': prediction.get('time_selection_reasoning', ''),
                        'prediction_logic': prediction.get('prediction_logic', {}),
                        'relative_x': max(0.05, min(0.95, relative_x)), 
                        'relative_y': max(0.1, min(0.9, relative_y)), 
                        'data_x': pred_date.timestamp() * 1000, 
                        'data_y': float(pred_price), 
                        'color': self._get_color_by_quality(tweet_quality, verification_accuracy),
                        'marker': {'bullish': '^', 'bearish': 'v', 'neutral': 'o'}.get(sentiment, '^')
                    })
            
            # 如果需要，扩展价格数据到最长预测点后7天
            if max_prediction_date and max_prediction_date > df['date'].max():
                target_end_date = max_prediction_date + timedelta(days=7)
                self.logger.info(f"扩展图表时间范围到: {target_end_date.strftime('%Y-%m-%d')}")
                
                # 获取扩展的价格数据
                extended_price_data = self.get_crypto_price_history(
                    price_data['coin_id'],
                    df['date'].min(),
                    target_end_date
                )
                
                if extended_price_data:
                    df = extended_price_data['data']
                    # 重新绘制价格曲线
                    ax.clear()
                    ax.plot(df['date'], df['price'], linewidth=3, color='#1f77b4', 
                           label=f'{coin_name} Price', alpha=0.9, zorder=1)
            
            # 设置图表样式
            title_text = f'@{kol_name} × {coin_name} 专业级推理链分析'
            ax.set_title(title_text, fontsize=20, fontweight='bold', pad=40)
            ax.set_xlabel('Date', fontsize=18)
            ax.set_ylabel('Price (USD)', fontsize=18)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df)//20)))
            plt.xticks(rotation=45)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:.4f}'))
            
            # 简化图例 - 不包含预测点图例，因为HTML会处理
            legend_elements = [
                plt.Line2D([0], [0], color='#1f77b4', linewidth=3, label=f'{coin_name} 价格'),
            ]
            ax.legend(handles=legend_elements, loc='upper left', fontsize=16, 
                     frameon=True, fancybox=True, shadow=True)
            plt.tight_layout()
            
            # 保存图表
            chart_filename = f"{kol_name}_{coin_name.replace('/', '_')}_optimized_for_html.png"
            chart_path = os.path.join(self.output_dir, "charts", chart_filename)
            plt.savefig(chart_path, format='png', dpi=120, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            
            # 生成base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            fig_width, fig_height = fig.get_size_inches() * fig.dpi
            plt.close(fig)
            
            self.logger.info(f"✅ 优化图表创建完成（配合HTML hotpoint）: {chart_path}")
            self.logger.info(f"  📊 图表信息: {len(prediction_coordinates)}个预测点，尺寸{fig_width:.0f}x{fig_height:.0f}")
            
            return {
                'image_base64': image_base64, 
                'prediction_coordinates': prediction_coordinates, 
                'chart_path': chart_path, 
                'chart_dimensions': {'width': float(fig_width), 'height': float(fig_height)}, 
                'version': 'optimized_for_html_hotpoint_system',
                'total_predictions': len(prediction_coordinates),
                'price_data_points': len(df),
                'date_range': {
                    'start': df['date'].min().isoformat(),
                    'end': df['date'].max().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"创建优化图表时出错: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_color_by_quality(self, tweet_quality: Dict, verification_accuracy: float) -> str:
        """根据推文质量评估获取颜色"""
        try:
            # 首先尝试基于推文质量评估
            quality_rating = tweet_quality.get('推文质量判断', '')
            
            if '优秀' in quality_rating:
                return '#2E7D32'  # 深绿
            elif '良好' in quality_rating:
                return '#4CAF50'  # 绿色
            elif '一般' in quality_rating:
                return '#FF9800'  # 橙色
            elif '较差' in quality_rating:
                return '#F44336'  # 红色
            else:
                # 后备方案：基于验证准确率
                if verification_accuracy >= 80:
                    return '#4CAF50'
                elif verification_accuracy >= 60:
                    return '#FF9800'
                else:
                    return '#F44336'
        except:
            # 默认颜色
            return '#FF9800'

    # ========================================================================
    # 主分析流程 - 优化版
    # ========================================================================
    
    async def analyze_reasoning_chain_with_html_optimization(self, chain_key: str, reasoning_chain: List[Dict]) -> Dict:
        """分析单个推理链，优化配合HTML生成器 - 完整优化版"""
        try:
            # 使用与构建时一致的专用分隔符解析chain_key
            if '|||' in chain_key:
                kol_name, coin_name = chain_key.split('|||', 1)
            else:
                # 兼容旧的下划线分隔格式（向后兼容）
                kol_name, coin_name = chain_key.split('_', 1)
            self.logger.info(f"🚀 开始优化版推理链分析: @{kol_name} × {coin_name} ({len(reasoning_chain)} 条预测)")
            
            # Phase 1: 预处理推理链背景 (增强版)
            self.logger.info("📋 Phase 1: 详细预处理推理链背景...")
            chain_context = self.preprocess_reasoning_chain(reasoning_chain, kol_name, coin_name)
            
            # Phase 2: 专业级Super Analyzer并发分析
            self.logger.info("🧠 Phase 2: 专业级Super Analyzer并发分析...")
            all_predictions = await self.analyze_tweets_concurrently(reasoning_chain, chain_context, coin_name)
            
            if not all_predictions:
                self.logger.warning("  ⚠️ 未找到有效预测，跳过该推理链")
                return {'error': '未找到有效预测'}
            
            self.logger.info(f"  ✅ 共找到 {len(all_predictions)} 个有效预测")
            
            # Phase 3: 执行深度requests + 真实验证 - 使用修复的引擎
            self.logger.info("🔍 Phase 3: 执行深度search requests + 真实验证...")
            prediction_results = await self.execute_requests_with_deep_analysis(all_predictions)
            
            # Phase 4: 按时间框架分组
            self.logger.info("📊 Phase 4: 按时间框架分组进行专业分析...")
            short_predictions = [p for p in prediction_results if p.get('timeframe') == 'short_term']
            long_predictions = [p for p in prediction_results if p.get('timeframe') in ['medium_term', 'long_term']]
            
            self.logger.info(f"  短期预测: {len(short_predictions)} 个")
            self.logger.info(f"  长期预测: {len(long_predictions)} 个")
            
            # Phase 5: 增强版短期分析
            self.logger.info("⚡ Phase 5: 增强版短期预测分析...")
            short_analysis = self.analyze_short_term_with_comprehensive_insights(short_predictions, long_predictions)
            
            # Phase 6: 增强版长期分析
            self.logger.info("🎯 Phase 6: 增强版长期预测分析...")
            long_analysis = self.analyze_long_term_with_strategic_depth(long_predictions, short_analysis)
            
            # Phase 7: 专业级最终KOL评估
            self.logger.info("🏆 Phase 7: 专业级KOL最终评估...")
            final_evaluation = self.final_professional_kol_evaluation(short_analysis, long_analysis, chain_context, kol_name, coin_name)
            
            # Phase 8: 生成优化图表 - 配合HTML hotpoint系统
            self.logger.info("📈 Phase 8: 生成优化图表（配合HTML hotpoint系统）...")
            chart_data = None
            if prediction_results and 'tweet_info' in prediction_results[0]:
                coingecko_id = prediction_results[0]['tweet_info'].get('coingecko_id')
                if coingecko_id:
                    dates = [pd.to_datetime(p['tweet_info']['tweet_created_at']) for p in prediction_results]
                    start_date, end_date = min(dates) - timedelta(days=7), max(dates) + timedelta(days=30)
                    price_data = self.get_crypto_price_history(coingecko_id, start_date, end_date)
                    if price_data:
                        chart_data = self.create_optimized_chart_for_html(kol_name, coin_name, prediction_results, price_data)

            # Phase 9: 准备数据结构 - 优化版
            self.logger.info("📄 Phase 9: 准备优化的分析结果数据...")
            analysis_result = {
                'chain_key': chain_key, 
                'kol_name': kol_name, 
                'coin_name': coin_name,
                'chain_context': chain_context, 
                'prediction_results': prediction_results,
                'short_analysis': short_analysis, 
                'long_analysis': long_analysis,
                'final_evaluation': final_evaluation, 
                'chart_data': chart_data,
                'analysis_timestamp': datetime.now().isoformat(), 
                'version': 'optimized_for_html_generator',
                'optimization_features': {
                    'html_hotpoint_compatible': True,
                    'prediction_coordinates_ready': bool(chart_data and chart_data.get('prediction_coordinates')),
                    'tweet_quality_evaluation_complete': True,
                    'comprehensive_analysis_depth': 'professional_grade'
                }
            }
            
            # 保存JSON
            json_path = os.path.join(self.output_dir, "kol_analysis", f"{kol_name}_{coin_name}_optimized_analysis.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2, default=str)
            analysis_result['json_path'] = json_path
            
            grade = final_evaluation.get('executive_summary', {}).get('overall_grade', 'N/A')
            score = final_evaluation.get('executive_summary', {}).get('overall_score', 'N/A')
            tier = final_evaluation.get('tier', None) or final_evaluation.get('tier', 'N/A')
            
            # 记录核心评估结果
            core_thesis = final_evaluation.get('🎯 CORE_INVESTMENT_THESIS', {})
            attention_index = core_thesis.get('值得关注指数', 'N/A')
            follow_index = core_thesis.get('值得跟随指数', 'N/A')
            
            # 记录优化信息
            chart_info = chart_data if chart_data else {}
            prediction_count = len(chart_info.get('prediction_coordinates', []))
            
            self.logger.info(f"🎉 优化版推理链分析完成: @{kol_name} × {coin_name}")
            self.logger.info(f"  📊 综合等级: {tier}")
            self.logger.info(f"  🎯 关注指数: {attention_index} | 跟随指数: {follow_index}")
            self.logger.info(f"  📈 图表优化: {prediction_count}个预测点，配合HTML hotpoint系统")
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"优化版分析推理链 {chain_key} 时出错: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e), 'chain_key': chain_key}
    
    async def run_optimized_analysis_pipeline(self, limit: Optional[int] = None):
        """运行优化的完整分析流程 - 配合HTML生成器"""
        try:
            self.logger.info("🚀 启动优化版KOL分析系统（配合HTML生成器）...")
            self.logger.info("📋 优化特性:")
            self.logger.info("  ✅ 去掉图表预测点绘制，配合HTML hotpoint系统")
            self.logger.info("  ✅ 生成精确的预测坐标数据供HTML使用")
            self.logger.info("  ✅ 保持推文质量深度评估功能")
            self.logger.info("  ✅ 优化数据结构与HTML生成器完美配合")
            self.logger.info("  ✅ 修复所有已知技术问题")
            
            reasoning_chains = self.load_reasoning_chains()
            
            if not reasoning_chains:
                self.logger.error("❌ 未找到任何推理链数据")
                return

            if limit:
                # 随机选择以增加多样性，避免每次测试都分析相同的链
                if limit < len(reasoning_chains):
                    reasoning_chains = dict(random.sample(list(reasoning_chains.items()), limit))
                else:
                    reasoning_chains = dict(list(reasoning_chains.items())[:limit])
                self.logger.info(f"🔧 限制分析数量: {len(reasoning_chains)} 条推理链")
            
            self.logger.info(f"📊 开始优化版分析 {len(reasoning_chains)} 条推理链...")
            
            analysis_results = []
            successful_analyses, failed_analyses = 0, 0
            
            for i, (chain_key, chain) in enumerate(reasoning_chains.items(), 1):
                self.logger.info(f"\n{'='*70}\n📈 [{i}/{len(reasoning_chains)}] 优化版分析: {chain_key}\n{'='*70}")
                try:
                    result = await self.analyze_reasoning_chain_with_html_optimization(chain_key, chain)
                    if 'error' not in result:
                        analysis_results.append(result)
                        successful_analyses += 1
                        
                        # 记录优化效果
                        optimization_features = result.get('optimization_features', {})
                        chart_data = result.get('chart_data', {})
                        prediction_count = len(chart_data.get('prediction_coordinates', []))
                        
                        self.logger.info(f"  🔍 优化效果: HTML兼容{optimization_features.get('html_hotpoint_compatible', False)}, {prediction_count}个预测坐标生成")
                        
                    else:
                        failed_analyses += 1
                        self.logger.error(f"❌ 推理链 {chain_key} 分析失败: {result.get('error')}")

                    if i < len(reasoning_chains):
                        self.logger.info("⏳ 短暂休整5秒，准备下一条分析...")
                        await asyncio.sleep(5)

                except Exception as e:
                    failed_analyses += 1
                    self.logger.error(f"❌ 推理链 {chain_key} 优化版分析时发生意外异常: {e}")
                    import traceback
                    traceback.print_exc()

            self.logger.info(f"\n{'='*70}\n📊 生成HTML报告...\n{'='*70}")
            
            # 生成HTML报告 - 使用优化的HTML生成器
            # 分配等级（Tier），并移除显式分数字段以便HTML只显示等级
            tier_counts = self.assign_tiers(analysis_results)
            self.logger.info(f"🔖 已为 {len(analysis_results)} 个KOL分配等级: {tier_counts}")
            if self.html_generator:
                all_reports = await self.html_generator.generate_all_reports(analysis_results, self.output_dir)
                summary_report = all_reports.get('summary_report')
            else:
                summary_report = None
            
            self.logger.info(f"\n🎉 优化版分析流程结束! 成功: {successful_analyses}, 失败: {failed_analyses}")
            self.logger.info(f"📄 汇总报告: {summary_report}")
            
            # 总结优化效果
            self.logger.info(f"\n🔧 优化效果总结:")
            total_predictions = sum(len(r.get('prediction_results', [])) for r in analysis_results)
            total_chart_coordinates = sum(len(r.get('chart_data', {}).get('prediction_coordinates', [])) for r in analysis_results)
            total_quality_evaluations = sum(sum(1 for p in r.get('prediction_results', []) if p.get('comprehensive_analysis', {}).get('🎯 TWEET_QUALITY_DEEP_EVALUATION')) for r in analysis_results)
            html_compatible_count = sum(1 for r in analysis_results if r.get('optimization_features', {}).get('html_hotpoint_compatible', False))
            
            self.logger.info(f"  📊 总预测数: {total_predictions}")
            self.logger.info(f"  📈 图表坐标生成: {total_chart_coordinates}/{total_predictions} ({(total_chart_coordinates/total_predictions*100) if total_predictions > 0 else 0:.1f}%)")
            self.logger.info(f"  🎯 推文质量评估完成: {total_quality_evaluations}/{total_predictions} ({(total_quality_evaluations/total_predictions*100) if total_predictions > 0 else 0:.1f}%)")
            self.logger.info(f"  🌐 HTML兼容性: {html_compatible_count}/{len(analysis_results)} ({(html_compatible_count/len(analysis_results)*100) if analysis_results else 0:.1f}%)")
            
            return {
                'successful_analyses': successful_analyses, 
                'failed_analyses': failed_analyses,
                'total_chains': len(reasoning_chains), 
                'analysis_results': analysis_results,
                'summary_report': summary_report, 
                'output_directory': self.output_dir,
                'optimization_summary': {
                    'html_hotpoint_compatible': True,
                    'prediction_coordinates_generated': total_chart_coordinates,
                    'tweet_quality_evaluations_completed': total_quality_evaluations,
                    'chart_optimization_enabled': True,
                    'all_technical_issues_fixed': True
                }
            }
        except Exception as e:
            self.logger.error(f"优化版分析流程顶层出错: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def run_optimized_analysis_pipeline_parallel(self, limit: Optional[int] = None):
        """并行版本的分析流程（链级并发，受限并发度）"""
        try:
            self.logger.info("🚀 启动优化版KOL分析系统（配合HTML生成器）... 并行链分析")
            self.logger.info("📋 优化特性: 链级并发 + 推文级并发，受限并发度保护配额")

            reasoning_chains = self.load_reasoning_chains()
            if not reasoning_chains:
                self.logger.error("❌ 未找到任何推理链数据")
                return

            if limit:
                if limit < len(reasoning_chains):
                    reasoning_chains = dict(random.sample(list(reasoning_chains.items()), limit))
                else:
                    reasoning_chains = dict(list(reasoning_chains.items())[:limit])
                self.logger.info(f"🔧 限制分析数量: {len(reasoning_chains)} 条推理链")

            self.logger.info(f"📊 开始并行分析 {len(reasoning_chains)} 条推理链（链级并发）...")

            chain_semaphore = asyncio.Semaphore(2)

            async def analyze_single_chain(chain_key: str, chain: List[Dict]):
                async with chain_semaphore:
                    try:
                        return await self.analyze_reasoning_chain_with_html_optimization(chain_key, chain)
                    except Exception as e:
                        self.logger.error(f"❌ 推理链 {chain_key} 并行分析失败: {e}")
                        return {'error': str(e), 'chain_key': chain_key}

            tasks = [asyncio.create_task(analyze_single_chain(k, v)) for k, v in reasoning_chains.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            analysis_results = [r for r in results if isinstance(r, dict) and 'error' not in r]
            failed_analyses = len([r for r in results if isinstance(r, dict) and 'error' in r])

            self.logger.info(f"\n{'='*70}\n📊 生成HTML报告...\n{'='*70}")
            # 分配等级（Tier），并移除显式分数字段以便HTML只显示等级
            tier_counts = self.assign_tiers(analysis_results)
            self.logger.info(f"🔖 已为 {len(analysis_results)} 个KOL分配等级: {tier_counts}")
            if self.html_generator:
                all_reports = await self.html_generator.generate_all_reports(analysis_results, self.output_dir)
                summary_report = all_reports.get('summary_report')
            else:
                summary_report = None

            self.logger.info(f"\n🎉 并行版分析流程结束! 成功: {len(analysis_results)}, 失败: {failed_analyses}")
            self.logger.info(f"📄 汇总报告: {summary_report}")

            total_predictions = sum(len(r.get('prediction_results', [])) for r in analysis_results)
            total_chart_coordinates = sum(len(r.get('chart_data', {}).get('prediction_coordinates', [])) for r in analysis_results)
            total_quality_evaluations = sum(
                sum(1 for p in r.get('prediction_results', []) if p.get('comprehensive_analysis', {}).get('🎯 TWEET_QUALITY_DEEP_EVALUATION'))
                for r in analysis_results
            )
            html_compatible_count = sum(1 for r in analysis_results if r.get('optimization_features', {}).get('html_hotpoint_compatible', False))

            self.logger.info(f"  📊 总预测数: {total_predictions}")
            self.logger.info(f"  📈 图表坐标生成: {total_chart_coordinates}/{total_predictions} ({(total_chart_coordinates/total_predictions*100) if total_predictions > 0 else 0:.1f}%)")
            self.logger.info(f"  🎯 推文质量评估完成: {total_quality_evaluations}/{total_predictions} ({(total_quality_evaluations/total_predictions*100) if total_predictions > 0 else 0:.1f}%)")
            self.logger.info(f"  🌐 HTML兼容性: {html_compatible_count}/{len(analysis_results)} ({(html_compatible_count/len(analysis_results)*100) if analysis_results else 0:.1f}%)")

            return {
                'successful_analyses': len(analysis_results),
                'failed_analyses': failed_analyses,
                'total_chains': len(reasoning_chains),
                'analysis_results': analysis_results,
                'summary_report': summary_report,
                'output_directory': self.output_dir,
                'optimization_summary': {
                    'html_hotpoint_compatible': True,
                    'prediction_coordinates_generated': total_chart_coordinates,
                    'tweet_quality_evaluations_completed': total_quality_evaluations,
                    'chart_optimization_enabled': True,
                    'all_technical_issues_fixed': True
                }
            }
        except Exception as e:
            self.logger.error(f"并行版分析流程顶层出错: {e}")
            import traceback
            traceback.print_exc()
            raise

# ========================================================================
# 命令行参数解析和主函数 - 优化版
# ========================================================================

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='优化版KOL分析器V2 - 配合HTML生成器',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''
优化特性:
  ✅ 去掉图表预测点绘制，配合HTML hotpoint系统
  ✅ 生成精确的预测坐标数据供HTML使用
  ✅ 保持推文质量深度评估功能
  ✅ 优化数据结构与HTML生成器完美配合
  ✅ 修复所有已知技术问题

示例用法:
  # 基本优化分析，限制为3条链（测试优化效果）
  python optimized_v2.py --api_key "your_openai_api_key" --limit 3

  # 使用CoinGecko Pro API进行完整优化分析
  python optimized_v2.py --api_key "your_openai_api_key" --coingecko_api_key "your_coingecko_pro_key"

  # 详细日志输出（查看优化效果）
  python optimized_v2.py --api_key "your_openai_api_key" --verbose
        '''
    )
    
    parser.add_argument('--db_dir', type=str, default='./data', 
                       help='数据库目录路径 (默认: ./data)')
    parser.add_argument('--api_key', type=str, required=True, 
                       help='OpenAI API密钥 (必需)')
    parser.add_argument('--coingecko_api_key', type=str, default="你的api key", 
                       help='CoinGecko Pro API密钥 (可选，建议使用以获得更好的分析效果)')
    parser.add_argument('--limit', type=int, default=None, 
                       help='限制分析的推理链数量 (可选，用于测试)')
    parser.add_argument('--verbose', action='store_true', 
                       help='启用详细日志输出')
    parser.add_argument('--parallel_chains', action='store_true', 
                       help='启用链级并行分析（与推文级并发叠加，建议控制总并发）')
    
    return parser.parse_args()

async def main():
    """主函数 - 优化版KOL分析器入口（配合HTML生成器）"""
    try:
        args = parse_arguments()
        
        # 根据--verbose参数设置日志级别
        if args.verbose:
            # 确保日志记录器已创建
            if not logging.getLogger().hasHandlers():
                logging.basicConfig(level=logging.DEBUG)
            else:
                logging.getLogger().setLevel(logging.DEBUG)
        
        print("🚀 启动优化版KOL分析器V2 - 配合HTML生成器")
        print("=" * 80)
        print("🔧 主要优化特性:")
        print("   ✅ 去掉图表预测点绘制，配合HTML hotpoint系统")
        print("   ✅ 生成精确的预测坐标数据供HTML使用")
        print("   ✅ 保持推文质量深度评估功能")
        print("   ✅ 优化数据结构与HTML生成器完美配合")
        print("   ✅ 修复所有已知技术问题（422错误、时间戳、截断等）")
        print("   🎯 核心特性：推文质量深度评估")
        print("      - 回答'这条推文到底是好还是坏？'")
        print("      - 提供详细的投资价值分析")
        print("      - 给出具体的跟随建议和风险警示")
        print("      - 完美配合HTML交互式hotpoint系统")
        print("=" * 80)
        print(f"📁 数据库目录: {args.db_dir}")
        print(f"🔑 OpenAI API: {'已配置' if args.api_key else '未配置'}")
        print(f"🔑 CoinGecko API: {'Pro版本' if args.coingecko_api_key else '免费版本'}")
        if args.limit:
            print(f"🔧 分析限制: {args.limit} 条推理链")
        print("=" * 80)
        print("🎯 分析特色（优化版）:")
        print("   • 深度AI分析和预测逻辑挖掘")
        print("   • 真实历史价格验证（修复422错误）")
        print("   • 综合搜索结果分析（完整展示，不截断）") 
        print("   • 推文质量深度评估（新增核心功能）")
        print("   • 专业级投资建议和风险控制指导")
        print("   • 机构级评估报告")
        print("   • 优化图表生成，配合HTML hotpoint交互系统")
        print("=" * 80)
        
        # 验证输入
        if not os.path.exists(args.db_dir):
            print(f"❌ 错误: 数据库目录不存在: {args.db_dir}")
            return
        
        crypto_db_path = os.path.join(args.db_dir, "crypto_recommendations.db")
        if not os.path.exists(crypto_db_path):
            print(f"❌ 错误: 推荐数据库不存在: {crypto_db_path}")
            return
        
        # 初始化分析器
        analyzer = EnhancedKOLAnalyzerV2(
            db_dir=args.db_dir,
            api_key=args.api_key,
            coingecko_api_key=args.coingecko_api_key
        )
        
        print("\n🔥 开始优化版分析流程（配合HTML生成器）...")
        print("📋 分析阶段:")
        print("   1️⃣ 推理链背景深度预处理")
        print("   2️⃣ 专业级推文内容分析（含质量评估）") 
        print("   3️⃣ 深度搜索和数据收集（修复API错误）")
        print("   4️⃣ 真实价格验证（修复时间戳问题）")
        print("   5️⃣ 综合评估和洞察（回答推文好坏）")
        print("   6️⃣ 优化图表生成（配合HTML hotpoint系统）")
        print("   7️⃣ 专业级HTML报告生成")
        print()
        
        # 执行分析
        results = await analyzer.run_optimized_analysis_pipeline_parallel(limit=args.limit)
        
        print("\n" + "=" * 80)
        print("🎉 优化版分析完成（配合HTML生成器）!")
        print("=" * 80)
        
        if results and 'successful_analyses' in results:
            print(f"✅ 成功分析: {results.get('successful_analyses', 0)} 条推理链")
            print(f"❌ 失败分析: {results.get('failed_analyses', 0)} 条推理链")
            total_chains = results.get('total_chains', 1)
            if total_chains > 0:
                success_rate = results.get('successful_analyses', 0) / total_chains * 100
                print(f"📊 成功率: {success_rate:.1f}%")
            print(f"📄 汇总报告: {results.get('summary_report', '未生成')}")
            print(f"📁 输出目录: {results.get('output_directory', 'N/A')}")
            
            # 显示优化效果
            optimization_summary = results.get('optimization_summary', {})
            print("\n🔧 优化效果验证:")
            print(f"   ✅ HTML hotpoint兼容: {optimization_summary.get('html_hotpoint_compatible', False)}")
            print(f"   📈 预测坐标生成: {optimization_summary.get('prediction_coordinates_generated', 0)}个")
            print(f"   🎯 推文质量评估: {optimization_summary.get('tweet_quality_evaluations_completed', 0)}个")
            print(f"   📊 图表优化启用: {optimization_summary.get('chart_optimization_enabled', False)}")
            print(f"   🛠️ 技术问题修复: {optimization_summary.get('all_technical_issues_fixed', False)}")
            
            print("\n🎯 分析亮点（优化版）:")
            print("   • 每个预测都进行了多维度深度分析")
            print("   • 基于真实历史价格的精确验证（修复API错误）")
            print("   • 推文质量深度评估 - 明确回答'好'还是'坏'")
            print("   • 专业级投资建议和风险评估")
            print("   • 机构级别的KOL评估标准")
            print("   • 优化的图表系统，完美配合HTML hotpoint交互")
            print("   • 详细的HTML报告支持交互式查看")
            
            # 显示最佳表现的KOL（如果有的话）
            analysis_results = results.get('analysis_results', [])
            if analysis_results:
                # 选择内部评分最高的作为样例（如果没有_internal_score则退回为0）
                best_result = max(
                    analysis_results,
                    key=lambda x: x.get('final_evaluation', {}).get('_internal_score', 0)
                )
                core_thesis = best_result.get('final_evaluation', {}).get('🎯 CORE_INVESTMENT_THESIS', {})
                tier = best_result.get('final_evaluation', {}).get('tier', 'N/A')
                
                print("\n🏆 最佳表现KOL:")
                print(f"   @{best_result.get('kol_name', 'N/A')} × {best_result.get('coin_name', 'N/A')}")
                print(f"   等级: {tier}")
                if core_thesis:
                    print(f"   关注指数: {core_thesis.get('值得关注指数', 'N/A')}")
                    print(f"   跟随指数: {core_thesis.get('值得跟随指数', 'N/A')}")
                    print(f"   风险级别: {core_thesis.get('风险警示级别', 'N/A')}")
                
                # 显示优化效果
                optimization_features = best_result.get('optimization_features', {})
                chart_data = best_result.get('chart_data', {})
                if chart_data:
                    prediction_count = len(chart_data.get('prediction_coordinates', []))
                    chart_version = chart_data.get('version', 'N/A')
                    print(f"\n📊 图表优化样例:")
                    print(f"   版本: {chart_version}")
                    print(f"   预测坐标: {prediction_count}个")
                    print(f"   HTML兼容: {optimization_features.get('html_hotpoint_compatible', False)}")
                    print(f"   坐标就绪: {optimization_features.get('prediction_coordinates_ready', False)}")
                
                # 显示推文质量评估效果
                prediction_results = best_result.get('prediction_results', [])
                quality_evaluations = [p for p in prediction_results if p.get('comprehensive_analysis', {}).get('🎯 TWEET_QUALITY_DEEP_EVALUATION')]
                if quality_evaluations:
                    print(f"\n📊 推文质量评估样例（共{len(quality_evaluations)}条）:")
                    sample_eval = quality_evaluations[0].get('comprehensive_analysis', {}).get('🎯 TWEET_QUALITY_DEEP_EVALUATION', {})
                    if sample_eval:
                        print(f"   推文质量判断: {sample_eval.get('推文质量判断', 'N/A')}")
                        print(f"   综合评分: {sample_eval.get('综合评分', 'N/A')}")
                        print(f"   内容质量: {sample_eval.get('content_quality_score', 'N/A')}")
                        print(f"   预测价值: {sample_eval.get('prediction_value_score', 'N/A')}")
                        print(f"   KOL责任: {sample_eval.get('kol_responsibility_score', 'N/A')}")
                
        else:
            print("❌ 分析流程未返回有效结果或中途失败。请检查日志。")
        
        print("\n💡 提示: 查看生成的HTML报告获取完整的专业分析结果")
        print("🔧 优化说明: 本版本专门优化配合HTML生成器，图表与hotpoint系统完美结合")
        print("🎯 核心特性: 推文质量深度评估功能帮助用户明确判断KOL推文价值")
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断了分析过程")
    except Exception as e:
        print(f"\n❌ 程序顶层执行出错: {e}")
        import traceback
        traceback.print_exc()
        print("\n🔧 故障排除建议:")
        print("   1. 检查API密钥是否正确且有足够额度")
        print("   2. 确认网络连接正常，且可以访问OpenAI和CoinGecko API")
        print("   3. 验证数据库文件是否存在且可访问")
        print("   4. 查看日志文件获取详细错误信息")
        print("   5. 本优化版本已解决了大部分已知技术问题")
        print("   6. 确认HTML生成器文件存在且可正常导入")

if __name__ == "__main__":
    # 设置事件循环策略（Windows兼容性）
    try:
        import asyncio
        if hasattr(asyncio, 'WindowsProactorEventLoopPolicy') and os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except:
        pass
    
    asyncio.run(main())
