# 这是加彩虹桥之前的版本
import os
import json
import logging
import requests
import hashlib
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
from urllib.parse import urlparse


class HTMLReportGenerator:
    """专业级HTML报告生成器 - 完整版本"""
    
    def __init__(self, template_dir: Optional[str] = None, coingecko_api_key: Optional[str] = None):
        self.logger = logging.getLogger("HTMLReportGenerator")
        self.kol_profiles = {}
        self.template_dir = template_dir or os.path.dirname(__file__)
        # 记录模块上一级的 data 目录作为备用位置（例如项目根的 data/）
        self.parent_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
        
        # 不在初始化时创建图片目录，改为在generate_all_reports时设置
        self.output_dir = None
        self.assets_dir = None
        self.images_dir = None
        
        # CoinGecko API 支持
        self.coingecko_api_key = coingecko_api_key
        if coingecko_api_key:
            self.coingecko_base_url = "https://pro-api.coingecko.com/api/v3"
            self.coingecko_headers = {"x-cg-pro-api-key": coingecko_api_key}
        else:
            self.coingecko_base_url = "https://api.coingecko.com/api/v3"
            self.coingecko_headers = {}

        # 会话对象（用于下载、API 请求复用）
        self.session = requests.Session()

        # 加载HTML模板
        self._load_templates()
    
    def _setup_output_directories(self, output_dir: str):
        """设置输出目录结构 - 修复版"""
        self.output_dir = output_dir
        self.assets_dir = os.path.join(output_dir, "assets")
        self.images_dir = os.path.join(self.assets_dir, "images")
        
        # 创建输出目录结构
        directories = [
            output_dir,
            os.path.join(output_dir, "kol_reports"),
            os.path.join(output_dir, "coin_reports"),
            self.assets_dir,
            self.images_dir
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            
        self.logger.info(f"✅ 输出目录结构创建完成：{self.images_dir}")
    
    def _download_image(self, url: str, username: str, image_type: str) -> Optional[str]:
        """下载图片到正确的输出目录并返回文件名（仅文件名，不含路径）"""
        try:
            if not url or not self.images_dir:
                self.logger.warning(f"图片URL为空或图片目录未设置: url={url}, images_dir={self.images_dir}")
                return None
                
            # 生成文件名
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            file_extension = os.path.splitext(urlparse(url).path)[1] or '.jpg'
            filename = f"{username}_{image_type}_{url_hash}{file_extension}"
            local_path = os.path.join(self.images_dir, filename)
            
            # 如果文件已存在，直接返回文件名
            if os.path.exists(local_path):
                self.logger.info(f"✅ 图片已存在: {filename}")
                return filename
            
            # 下载图片
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 保存图片
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            self.logger.info(f"✅ 下载图片成功: {local_path}")
            return filename
            
        except Exception as e:
            self.logger.error(f"下载图片失败 {url}: {e}")
            return None
    
    def _get_image_path(self, filename: str, html_level: str = 'root') -> str:
        """根据HTML文件层级生成正确的图片路径"""
        if not filename:
            return ''
        
        # 确保filename不包含路径前缀
        if '/' in filename:
            filename = os.path.basename(filename)
        
        # 根据HTML文件层级返回正确路径
        if html_level == 'root':
            return f"./assets/images/{filename}"
        else:
            return f"../assets/images/{filename}"
    
    def _generate_image_style(self, image_path: str, fallback_style: str = None) -> str:
        """生成完整的CSS背景样式"""
        if image_path and image_path.strip():
            return f"background-image: url('{image_path}'); background-size: cover; background-position: center;"
        else:
            # 使用默认渐变背景
            default_style = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);"
            return fallback_style or default_style

    def _get_coingecko_link(self, coin_name: str) -> Optional[str]:
        """尝试使用CoinGecko API查找币种对应的id并返回CoinGecko网页链接"""
        try:
            if not coin_name or not isinstance(coin_name, str):
                return None

            # 首先使用 search 端点
            params = {'query': coin_name}
            url = f"{self.coingecko_base_url}/search"
            resp = self.session.get(url, params=params, headers=self.coingecko_headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                coins = data.get('coins', [])
                # 优先精确匹配名称或符号
                for c in coins:
                    if c.get('name', '').lower() == coin_name.lower() or c.get('symbol', '').lower() == coin_name.lower():
                        coin_id = c.get('id')
                        return f"https://www.coingecko.com/en/coins/{coin_id}" if coin_id else None

                # 否则取第一个结果
                if coins:
                    coin_id = coins[0].get('id')
                    return f"https://www.coingecko.com/en/coins/{coin_id}" if coin_id else None

            # 退回到 coins/list 进行模糊匹配（当 search 不可用或没有结果时）
            url2 = f"{self.coingecko_base_url}/coins/list"
            resp2 = self.session.get(url2, headers=self.coingecko_headers, timeout=20)
            if resp2.status_code == 200:
                all_coins = resp2.json()
                name_lower = coin_name.lower()
                for c in all_coins:
                    if c.get('id', '').lower() == name_lower or c.get('symbol', '').lower() == name_lower or c.get('name', '').lower() == name_lower:
                        return f"https://www.coingecko.com/en/coins/{c.get('id')}"

                # 尝试部分匹配
                for c in all_coins:
                    if name_lower in c.get('name', '').lower() or name_lower in c.get('id', '').lower():
                        return f"https://www.coingecko.com/en/coins/{c.get('id')}"

            return None
        except Exception as e:
            self.logger.warning(f"CoinGecko链接获取失败 ({coin_name}): {e}")
            return None
    
    def _load_templates(self):
        """加载HTML模板文件"""
        try:
            template_files = {
                'kol_list': 'kol_list.html',
                'kol_coins': 'kol_coins.html',
                'coin_analysis': 'coin_analysis.html'
            }
            
            self.templates = {}
            
            for template_name, filename in template_files.items():
                template_path = os.path.join(self.template_dir, filename)
                
                if os.path.exists(template_path):
                    with open(template_path, 'r', encoding='utf-8') as f:
                        self.templates[template_name] = f.read()
                    self.logger.info(f"✅ 加载模板: {filename}")
                else:
                    self.logger.warning(f"⚠️ 模板文件不存在: {template_path}")
                    # 使用内置的基础模板
                    self.templates[template_name] = self._get_default_template(template_name)
                    
        except Exception as e:
            self.logger.error(f"加载模板失败: {e}")
            # 使用内置模板作为后备
            self.templates = {
                'kol_list': self._get_default_template('kol_list'),
                'kol_coins': self._get_default_template('kol_coins'),
                'coin_analysis': self._get_default_template('coin_analysis')
            }
    
    def _safe_get_value(self, data: Any, path: str, default: Any = '') -> Any:
        """安全地从嵌套字典中获取值"""
        try:
            keys = path.split('.')
            result = data
            for key in keys:
                if isinstance(result, dict):
                    result = result.get(key, default)
                else:
                    return default
            return result if result is not None else default
        except:
            return default
    
    def _safe_format_value(self, value: Any) -> str:
        """安全地格式化值为字符串"""
        if value is None:
            return ''
        elif isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        elif isinstance(value, list):
            return ', '.join(str(item) for item in value)
        else:
            return str(value)

    async def generate_all_reports(self, analysis_results: List[Dict], output_dir: str) -> Dict:
        """生成所有HTML报告 - 修复版"""
        try:
            self.logger.info("🎨 开始生成专业级HTML报告...")
            
            # 首先设置正确的输出目录
            self._setup_output_directories(output_dir)
            
            # 加载KOL profile数据并下载图片到正确位置
            await self._load_kol_profiles_with_download()
            
            # 收集和整理数据
            kol_summaries = {}
            coin_reports = []
            
            for result in analysis_results:
                if 'error' not in result:
                    try:
                        # 生成币种分析报告
                        coin_report = self.generate_coin_analysis_html(result)
                        coin_reports.append(coin_report)
                        
                        # 收集KOL汇总数据
                        self._collect_kol_summary(result, kol_summaries, coin_report)
                    except Exception as e:
                        self.logger.error(f"处理分析结果失败: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
            
            # 生成KOL个人报告
            kol_reports = []
            for kol_name, summary in kol_summaries.items():
                try:
                    kol_report = self.generate_kol_coins_html(kol_name, summary)
                    kol_reports.append(kol_report)
                    summary['report_path'] = kol_report
                except Exception as e:
                    self.logger.error(f"生成KOL报告失败 ({kol_name}): {e}")
                    continue
            
            # 生成KOL列表汇总报告
            try:
                summary_report = self.generate_kol_list_html(kol_summaries)
            except Exception as e:
                self.logger.error(f"生成汇总报告失败: {e}")
                summary_report = None
            
            self.logger.info(f"✅ HTML报告生成完成:")
            self.logger.info(f"   - 汇总报告: {'1个' if summary_report else '0个'}")
            self.logger.info(f"   - KOL报告: {len(kol_reports)}个")
            self.logger.info(f"   - 币种报告: {len(coin_reports)}个")
            self.logger.info(f"   - 总计: {len(coin_reports) + len(kol_reports) + (1 if summary_report else 0)}个报告")
            
            return {
                'summary_report': summary_report,
                'kol_reports': kol_reports,
                'coin_reports': coin_reports,
                'total_reports': len(coin_reports) + len(kol_reports) + (1 if summary_report else 0)
            }
            
        except Exception as e:
            self.logger.error(f"生成HTML报告失败: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    async def _load_kol_profiles_with_download(self):
        """加载KOL profiles并下载图片到正确位置 - 修复版"""
        try:
            self.logger.info("🔄 开始加载KOL profiles并下载图片...")
            
            # 确保输出目录已经设置
            if not self.images_dir:
                self.logger.error("❌ 图片目录未设置，无法下载图片")
                return
            
            # 查找kol_list.json文件：先尝试输出目录附近，其次尝试模块上一级的 data/，最后尝试当前工作目录或其他常见位置
            possible_paths = [
                os.path.join(os.path.dirname(self.output_dir), 'kol_list.json'),
                os.path.join(self.output_dir, 'kol_list.json'),
                os.path.join(self.template_dir, 'kol_list.json'),
                os.path.join(self.parent_data_dir, 'kol_list.json'),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'kol_list.json')),
                './kol_list.json'
            ]
            
            for profile_path in possible_paths:
                if os.path.exists(profile_path):
                    self.logger.info(f"📂 找到KOL profiles文件: {profile_path}")
                    
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                        
                        # 处理每个profile，确保图片下载到正确位置
                        for profile in profiles:
                            username = profile['username'].lower()
                            
                            self.logger.info(f"🔄 处理KOL profile: {username}")
                            
                            # 下载背景图片到正确位置，只存储文件名
                            if 'background' in profile and profile['background']:
                                self.logger.info(f"📥 开始下载背景图片: {profile['background']}")
                                local_bg_filename = self._download_image(
                                    profile['background'], 
                                    username, 
                                    'background'
                                )
                                if local_bg_filename:
                                    profile['local_background_filename'] = local_bg_filename
                                    self.logger.info(f"✅ 背景图片下载成功，文件名: {local_bg_filename}")
                                else:
                                    self.logger.warning(f"❌ 背景图片下载失败: {username}")
                                    profile['local_background_filename'] = None
                            else:
                                profile['local_background_filename'] = None
                                self.logger.info(f"⚠️ 没有背景图片URL: {username}")
                            
                            # 下载头像图片到正确位置，只存储文件名
                            if 'avatar' in profile and profile['avatar']:
                                self.logger.info(f"📥 开始下载头像图片: {profile['avatar']}")
                                local_avatar_filename = self._download_image(
                                    profile['avatar'], 
                                    username, 
                                    'avatar'
                                )
                                if local_avatar_filename:
                                    profile['local_avatar_filename'] = local_avatar_filename
                                    self.logger.info(f"✅ 头像图片下载成功，文件名: {local_avatar_filename}")
                                else:
                                    self.logger.warning(f"❌ 头像图片下载失败: {username}")
                                    profile['local_avatar_filename'] = None
                            else:
                                profile['local_avatar_filename'] = None
                                self.logger.info(f"⚠️ 没有头像图片URL: {username}")
                            
                            # 保存到kol_profiles中
                            self.kol_profiles[username] = profile
                        
                        self.logger.info(f"✅ 成功加载 {len(self.kol_profiles)} 个KOL profile，并下载了图片")
                        return
            
            self.logger.warning("⚠️ 未找到kol_list.json文件，将使用默认样式")
            
        except Exception as e:
            self.logger.error(f"加载KOL profiles失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _find_kol_profile(self, kol_name: str) -> Dict:
        """智能匹配KOL profile"""
        try:
            kol_name_lower = kol_name.lower()
            
            # 1. 精确匹配
            if kol_name_lower in self.kol_profiles:
                self.logger.info(f"✅ 精确匹配找到profile: {kol_name_lower}")
                return self.kol_profiles[kol_name_lower]
            
            # 2. 模糊匹配：查找包含kol_name的profile
            for profile_key, profile_data in self.kol_profiles.items():
                if kol_name_lower in profile_key or profile_key in kol_name_lower:
                    self.logger.info(f"✅ 模糊匹配找到profile: {kol_name_lower} -> {profile_key}")
                    return profile_data
            
            # 3. 尝试去除特殊字符后匹配
            import re
            kol_name_clean = re.sub(r'[^a-zA-Z0-9]', '', kol_name_lower)
            for profile_key, profile_data in self.kol_profiles.items():
                profile_key_clean = re.sub(r'[^a-zA-Z0-9]', '', profile_key)
                if kol_name_clean == profile_key_clean:
                    self.logger.info(f"✅ 清理后匹配找到profile: {kol_name_clean} -> {profile_key_clean}")
                    return profile_data
            
            self.logger.warning(f"❌ 未找到匹配的profile: {kol_name}")
            return {}
            
        except Exception as e:
            self.logger.error(f"查找KOL profile失败: {e}")
            return {}
    
    def _collect_kol_summary(self, result: Dict, kol_summaries: Dict, coin_report: str):
        """收集KOL汇总数据 - 修复版"""
        try:
            kol_name = result.get('kol_name', 'Unknown')
            if kol_name not in kol_summaries:
                # 智能匹配用户名
                profile = self._find_kol_profile(kol_name)
                
                # 获取文件名并生成完整路径
                bg_filename = profile.get('local_background_filename', '')
                avatar_filename = profile.get('local_avatar_filename', '')
                
                # 为根目录HTML生成正确的图片路径
                local_background_root = self._get_image_path(bg_filename, 'root') if bg_filename else ''
                local_avatar_root = self._get_image_path(avatar_filename, 'root') if avatar_filename else ''
                
                kol_summaries[kol_name] = {
                    'name': kol_name,
                    'coins': [],
                    'total_score': 0,
                    'total_accuracy': 0,
                    'coin_count': 0,
                    'profile': profile,
                    'local_background': local_background_root,
                    'local_avatar': local_avatar_root,
                    'background_filename': bg_filename,
                    'avatar_filename': avatar_filename,
                    'has_background': bool(bg_filename),
                    'has_avatar': bool(avatar_filename)
                }
            
            final_eval = result.get('final_evaluation', {})
            exec_summary = final_eval.get('executive_summary', {})
            comprehensive_verification = final_eval.get('comprehensive_verification_analysis', {})
            
            # 获取真实的准确率数据 - 添加安全处理
            short_term_perf = comprehensive_verification.get('short_term_performance', {})
            long_term_perf = comprehensive_verification.get('long_term_performance', {})
            integrated_perf = comprehensive_verification.get('integrated_performance', {})

            # 安全获取数值，处理 None 值
            def safe_get_float(value, default=0):
                if value is None:
                    return default
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return default

            # 使用与币种详情页相同的准确率计算方式
            # 计算按"通过的预测数 / 总预测数"定义的币种准确率
            predictions = result.get('prediction_results', []) or []
            total_preds = len(predictions)
            passed_preds = 0
            for p in predictions:
                rv = p.get('real_verification', {}) or {}
                try:
                    # 优先使用 explicit correct_count
                    cc = rv.get('correct_count')
                    if cc is not None:
                        if int(cc) > 0:
                            passed_preds += 1
                            continue
                except Exception:
                    pass

                try:
                    # 兼容历史字段：如果 overall_accuracy == 100 也视为通过
                    oa = rv.get('overall_accuracy')
                    if oa is not None:
                        try:
                            if float(oa) == 100.0:
                                passed_preds += 1
                                continue
                        except Exception:
                            pass
                except Exception:
                    pass

            overall_accuracy = (passed_preds / total_preds * 100.0) if total_preds > 0 else 0.0

            short_accuracy = safe_get_float(short_term_perf.get('avg_accuracy'), 0)
            long_accuracy = safe_get_float(long_term_perf.get('avg_accuracy'), 0)
            overall_score = safe_get_float(exec_summary.get('overall_score'), 60)
            
            coin_data = {
                'coin_name': str(result.get('coin_name', 'Unknown')),
                'coin_id': str(result.get('coin_name', 'unknown')).lower().replace(' ', '_').replace('/', '_'),
                'overall_accuracy': overall_accuracy,
                'short_term_accuracy': short_accuracy,
                'long_term_accuracy': long_accuracy,
                'grade': str(exec_summary.get('overall_grade', 'C')),
                'investment_grade': str(exec_summary.get('investment_grade', 'CAUTIOUS')),
                'report_path': str(coin_report),
                'total_predictions': len(result.get('prediction_results', [])),
                'performance_grade': str(exec_summary.get('overall_grade', 'C')),
                'summary': str(exec_summary.get('key_verdict', '')),
                'predictions': self._extract_prediction_summary(result),
                'tier': final_eval.get('tier', '')
            }
            
            kol_summaries[kol_name]['coins'].append(coin_data)
            kol_summaries[kol_name]['total_score'] += overall_score
            kol_summaries[kol_name]['total_accuracy'] += overall_accuracy
            kol_summaries[kol_name]['coin_count'] += 1
            # 更新KOL层面的tier（取最优）
            try:
                all_tiers = [c.get('tier') for c in kol_summaries[kol_name]['coins'] if c.get('tier')]
                tier_order = [
                    'S+', 'S', 'S-', 'A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-'
                ]
                tier_ranks = {t: i for i, t in enumerate(tier_order)}
                ranked = sorted([t for t in all_tiers if t in tier_ranks], key=lambda x: tier_ranks[x])
                kol_summaries[kol_name]['tier'] = ranked[0] if ranked else ''
            except Exception:
                kol_summaries[kol_name]['tier'] = kol_summaries[kol_name].get('tier', '')
            
        except Exception as e:
            self.logger.error(f"收集KOL汇总数据失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _extract_prediction_summary(self, result: Dict) -> List[Dict]:
        """提取预测摘要信息"""
        predictions = []
        try:
            for pred in result.get('prediction_results', [])[:5]:
                tweet_info = pred.get('tweet_info')
                real_verification = pred.get('real_verification', {})
                
                # 安全获取日期
                tweet_date = tweet_info.get('tweet_created_at', 'N/A') if tweet_info else 'N/A'
                if isinstance(tweet_date, str) and len(tweet_date) >= 10:
                    tweet_date = tweet_date[:10]
                else:
                    tweet_date = 'N/A'
                
                predictions.append({
                    'date': tweet_date,
                    'type': str(pred.get('timeframe', 'short_term')),
                    'sentiment': str(pred.get('sentiment', 'neutral')),
                    'accuracy': float(real_verification.get('overall_accuracy', 0) or 0)
                })
        except Exception as e:
            self.logger.error(f"提取预测摘要失败: {e}")
        
        return predictions

    def generate_coin_analysis_html(self, analysis_result: Dict) -> str:
        """生成币种分析HTML页面 - 完整修复版"""
        try:
            kol_name = analysis_result['kol_name']
            coin_name = analysis_result['coin_name']
            final_eval = analysis_result.get('final_evaluation', {})
            exec_summary = final_eval.get('executive_summary', {})
            comprehensive_verification = final_eval.get('comprehensive_verification_analysis', {})
            
            # 获取真实的准确率数据 - 添加安全检查
            short_term_perf = comprehensive_verification.get('short_term_performance', {})
            long_term_perf = comprehensive_verification.get('long_term_performance', {})
            integrated_perf = comprehensive_verification.get('integrated_performance', {})
            
            # 计算按“通过的预测数 / 总预测数”定义的币种准确率
            predictions = analysis_result.get('prediction_results', []) or []
            total_preds = len(predictions)
            passed_preds = 0
            for p in predictions:
                rv = p.get('real_verification', {}) or {}
                try:
                    # 优先使用 explicit correct_count
                    cc = rv.get('correct_count')
                    if cc is not None:
                        if int(cc) > 0:
                            passed_preds += 1
                            continue
                except Exception:
                    pass

                try:
                    # 兼容历史字段：如果 overall_accuracy == 100 也视为通过
                    oa = rv.get('overall_accuracy')
                    if oa is not None:
                        try:
                            if float(oa) == 100.0:
                                passed_preds += 1
                                continue
                        except Exception:
                            pass
                except Exception:
                    pass

            accuracy_val = (passed_preds / total_preds * 100.0) if total_preds > 0 else 0.0

            # 准备模板数据（币种页面仅显示单一的 `accuracy` 字段）
            template_data = {
                'kol_name': str(kol_name),
                'coin_name': str(coin_name),
                'kol_id': str(kol_name.lower().replace(' ', '_')),
                'total_predictions': total_preds,
                'accuracy': round(float(accuracy_val), 1),
                'time_span': self._calculate_time_span(analysis_result),
                'performance_grade': str(exec_summary.get('overall_grade', 'C'))
            }
            
            # 生成推文详情HTML
            tweet_details_html = []
            for i, pred in enumerate(analysis_result.get('prediction_results', [])):
                try:
                    tweet_html = self._generate_tweet_detail_html_complete(i, pred)
                    tweet_details_html.append(tweet_html)
                except Exception as e:
                    self.logger.error(f"生成推文详情HTML失败: {e}")
                    tweet_details_html.append(f"<div>推文 {i+1} 加载失败: {str(e)}</div>")
            
            template_data['tweet_details'] = '\n'.join(tweet_details_html)
            
            # 生成图表HTML
            if analysis_result.get('chart_data'):
                chart_data = analysis_result['chart_data']
                chart_html = f'<img src="data:image/png;base64,{chart_data["image_base64"]}" class="chart-image" alt="{coin_name}价格走势图" id="priceChartImg" />'
                template_data['chart_html'] = chart_html
                
                # 准备预测数据JSON
                coordinates = chart_data.get('prediction_coordinates', [])
                template_data['prediction_data_js'] = json.dumps(coordinates, ensure_ascii=False)
                
                # 准备价格数据（用于验证小图表）
                price_data = self._extract_price_data(analysis_result)
                template_data['price_data_js'] = json.dumps(price_data, ensure_ascii=False)
            else:
                template_data['chart_html'] = '<div style="padding: 50px; text-align: center; color: #666;">图表数据暂不可用</div>'
                template_data['prediction_data_js'] = '[]'
                template_data['price_data_js'] = '[]'
            
            # 生成CoinGecko链接（如果可用）
            try:
                coingecko_link = self._get_coingecko_link(coin_name)
            except Exception:
                coingecko_link = ''

            if coingecko_link:
                coingecko_link_html = f'<a class="nav-btn" href="{coingecko_link}" target="_blank">CoinGecko</a>'
            else:
                coingecko_link_html = ''

            template_data['coingecko_link_html'] = coingecko_link_html

            # 生成HTML：优先使用外部模板文件，其次使用内置模板作为后备
            html_content = self.templates.get('coin_analysis') or self._get_coin_analysis_template_complete()
            for key, value in template_data.items():
                html_content = html_content.replace(f'{{{key}}}', str(value))
            
            # 保存文件
            coin_id = coin_name.lower().replace(' ', '_').replace('/', '_')
            filename = f"{kol_name}_{coin_id}_analysis.html"
            filepath = os.path.join(self.output_dir, "coin_reports", filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"✅ 币种分析报告生成: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"生成币种分析HTML失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _extract_price_data(self, analysis_result: Dict) -> List[Dict]:
        """从分析结果中提取价格数据用于验证图表"""
        try:
            # 从prediction_results中获取价格信息
            prediction_results = analysis_result.get('prediction_results', [])
            price_points = []
            
            for pred in prediction_results:
                real_verification = pred.get('real_verification', {})
                base_price = real_verification.get('base_price')
                if base_price:
                    price_points.append({
                        'time': len(price_points),
                        'price': float(base_price)
                    })
            
            # 如果没有足够的数据点，生成模拟数据
            if len(price_points) < 120:
                base_price = price_points[0]['price'] if price_points else 45000
                price_data = []
                price = base_price
                
                for i in range(120):
                    price += (random.random() - 0.5) * 1500
                    price = max(38000, min(58000, price))
                    price_data.append({
                        'time': i,
                        'price': price
                    })
                return price_data
            
            return price_points
            
        except Exception as e:
            self.logger.error(f"提取价格数据失败: {e}")
            return self._generate_mock_price_data()
    
    def _generate_mock_price_data(self) -> List[Dict]:
        """生成模拟价格数据"""
        price_data = []
        price = 45000
        
        for i in range(120):
            price += (random.random() - 0.5) * 1500
            price = max(38000, min(58000, price))
            price_data.append({
                'time': i,
                'price': price
            })
        
        return price_data

    def _generate_tweet_detail_html_complete(self, index: int, prediction: Dict) -> str:
        """生成单个推文的详细HTML - 完整版本"""
        try:
            tweet_info = prediction.get('tweet_info', {})
            
            html = f'''
            <div class="tweet-detail-card">
                <div class="tweet-header">
                    <div>
                        <div class="tweet-title">预测 #{index+1}</div>
                        <div class="tweet-meta">
                            {self._safe_format_value(tweet_info.get('tweet_created_at', 'N/A'))} | 
                            {self._safe_format_value(prediction.get('timeframe', 'N/A'))} | 
                            {self._safe_format_value(prediction.get('sentiment', 'N/A'))}
                        </div>
                    </div>
                    <div class="expand-arrow" onclick="toggleTweetDetail({index})" id="arrow-{index}">▼</div>
                </div>
                
                <div class="collapsible-content" id="detail-{index}">
                    <div class="tweet-content">
                        {self._safe_format_value(tweet_info.get('full_tweet_text', 'N/A'))}
                    </div>
                    
                    <!-- AI分析 -->
                    <div class="analysis-section ai-analysis">
                        <div class="analysis-title">🤖 AI深度分析</div>
                        {self._format_ai_analysis_complete(prediction)}
                    </div>
                    
                    <!-- 搜索结果 - 完整版本 -->
                    <div class="analysis-section search-results">
                        <div class="analysis-title">🔍 搜索验证结果</div>
                        {self._format_search_results_complete(prediction)}
                    </div>
                    
                    <!-- 真实验证 -->
                    <div class="analysis-section verification-results">
                        <div class="analysis-title">✅ 真实价格验证</div>
                        {self._format_verification_results_complete(prediction)}
                    </div>
                    
                    <!-- 综合评估 -->
                    <div class="analysis-section comprehensive-analysis">
                        <div class="analysis-title">📊 综合评估</div>
                        {self._format_comprehensive_analysis_complete(prediction)}
                    </div>
                </div>
            </div>
            '''
            
            return html
        except Exception as e:
            self.logger.error(f"生成推文详情失败: {e}")
            return f'<div class="tweet-detail-card">推文 {index+1} 生成失败: {str(e)}</div>'
    
    def _format_ai_analysis_complete(self, prediction: Dict) -> str:
        """格式化AI分析结果 - 完整版"""
        try:
            content_analysis = prediction.get('content_analysis', {})
            prediction_logic = prediction.get('prediction_logic', {})
            
            html = '<div class="analysis-content">'
            
            # 基本信息
            html += f'<p><strong>内容类型:</strong> {self._safe_format_value(prediction.get("content_type", "N/A"))}</p>'
            html += f'<p><strong>情绪倾向:</strong> {self._safe_format_value(content_analysis.get("tone_analysis", "N/A"))}</p>'
            html += f'<p><strong>置信度:</strong> {self._safe_format_value(prediction.get("confidence_level", "N/A"))}</p>'
            
            # 预测逻辑
            if prediction_logic and isinstance(prediction_logic, dict):
                html += '<h4>预测逻辑分析</h4>'
                tech_basis = self._safe_format_value(prediction_logic.get('technical_basis', ''))
                fund_basis = self._safe_format_value(prediction_logic.get('fundamental_basis', ''))
                sent_basis = self._safe_format_value(prediction_logic.get('sentiment_basis', ''))
                
                if tech_basis:
                    html += f'<p><strong>技术面依据:</strong> {tech_basis}</p>'
                if fund_basis:
                    html += f'<p><strong>基本面依据:</strong> {fund_basis}</p>'
                if sent_basis:
                    html += f'<p><strong>市场情绪:</strong> {sent_basis}</p>'
            
            # 智能时间点选择
            check_points = prediction.get('intelligent_check_points', [])
            if check_points:
                html += '<h4>智能验证时间点</h4>'
                check_points_str = [self._safe_format_value(cp) for cp in check_points]
                html += '<p>' + ', '.join(check_points_str) + '</p>'
                
                time_reasoning = self._safe_format_value(prediction.get('time_selection_reasoning', ''))
                if time_reasoning:
                    html += f'<p><em>选择理由: {time_reasoning}</em></p>'
            
            html += '</div>'
            return html
            
        except Exception as e:
            self.logger.error(f"格式化AI分析失败: {e}")
            return f'<div class="analysis-content">AI分析数据格式化失败: {str(e)}</div>'
    
    def _format_search_results_complete(self, prediction: Dict) -> str:
        """格式化完整搜索结果 - 完整版本，整合手风琴展示"""
        try:
            # 获取搜索结果数据
            request_results = prediction.get('request_results', [])
            results_analysis = prediction.get('results_analysis', {})
            
            if not request_results and not results_analysis:
                return '<div class="analysis-content">暂无搜索验证数据</div>'
            
            html = '<div class="search-results-accordion">'
            
            # 1. 详细洞察
            if results_analysis.get('detailed_insights'):
                detailed_insights = results_analysis['detailed_insights']
                html += f'''
                <div class="accordion-item">
                    <div class="accordion-summary" onclick="toggleSearchAccordion(this)">
                        <span>💡 详细洞察 ({len(detailed_insights)}项)</span>
                        <span class="accordion-icon">▼</span>
                    </div>
                    <div class="accordion-content">
                        <div class="accordion-inner">
                '''
                
                for insight in detailed_insights:
                    category = self._translate_category(insight.get('category', '未分类'))
                    insight_content = self._safe_format_value(insight.get('insight', ''))
                    supporting_data = self._safe_format_value(insight.get('supporting_data', ''))
                    relevance_score = insight.get('relevance_score', 0)
                    impact = self._translate_impact(insight.get('impact_assessment', 'neutral'))
                    
                    html += f'''
                    <div class="insight-item">
                        <div class="insight-category">{category}</div>
                        <div class="insight-content">{insight_content}</div>
                        {f'<div class="supporting-data"><strong>支撑数据：</strong><br>{supporting_data}</div>' if supporting_data else ''}
                        <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
                            <span class="score-badge">相关性：{relevance_score}/100</span>
                            <span class="impact-badge impact-{insight.get('impact_assessment', 'neutral')}">{impact}</span>
                        </div>
                    </div>
                    '''
                
                html += '''
                        </div>
                    </div>
                </div>
                '''
            
            # 2. 支持证据
            if results_analysis.get('supporting_evidence'):
                supporting_evidence = results_analysis['supporting_evidence']
                html += f'''
                <div class="accordion-item">
                    <div class="accordion-summary" onclick="toggleSearchAccordion(this)">
                        <span>✅ 支持证据 ({len(supporting_evidence)}项)</span>
                        <span class="accordion-icon">▼</span>
                    </div>
                    <div class="accordion-content">
                        <div class="accordion-inner">
                '''
                
                for evidence in supporting_evidence:
                    evidence_type = self._translate_evidence_type(evidence.get('evidence_type', '未知'))
                    description = self._safe_format_value(evidence.get('description', ''))
                    strength = self._translate_strength(evidence.get('strength', 'unknown'))
                    timeframe_relevance = self._translate_relevance(evidence.get('timeframe_relevance', ''))
                    
                    html += f'''
                    <div class="evidence-item">
                        <div class="evidence-header">
                            <span class="evidence-type">{evidence_type}</span>
                            <span class="evidence-strength strength-{evidence.get('strength', 'unknown')}">{strength}</span>
                        </div>
                        <div class="evidence-description">{description}</div>
                        {f'<div class="evidence-relevance">时效性：{timeframe_relevance}</div>' if timeframe_relevance else ''}
                    </div>
                    '''
                
                html += '''
                        </div>
                    </div>
                </div>
                '''
            
            # 3. 反驳证据
            if results_analysis.get('contradictory_evidence'):
                contradictory_evidence = results_analysis['contradictory_evidence']
                html += f'''
                <div class="accordion-item">
                    <div class="accordion-summary" onclick="toggleSearchAccordion(this)">
                        <span>❌ 反驳证据 ({len(contradictory_evidence)}项)</span>
                        <span class="accordion-icon">▼</span>
                    </div>
                    <div class="accordion-content">
                        <div class="accordion-inner">
                '''
                
                for evidence in contradictory_evidence:
                    evidence_type = self._translate_evidence_type(evidence.get('evidence_type', '未知'))
                    description = self._safe_format_value(evidence.get('description', ''))
                    impact = self._translate_impact_level(evidence.get('impact', 'unknown'))
                    
                    html += f'''
                    <div class="evidence-item evidence-negative">
                        <div class="evidence-header">
                            <span class="evidence-type">{evidence_type}</span>
                            <span class="evidence-impact impact-{evidence.get('impact', 'unknown')}">{impact}</span>
                        </div>
                        <div class="evidence-description">{description}</div>
                    </div>
                    '''
                
                html += '''
                        </div>
                    </div>
                </div>
                '''
            
            # 4. CoinGecko研究结果
            coingecko_results = []
            for result in request_results:
                if result.get('request', {}).get('type') == 'coingecko_api':
                    coingecko_results.append(result)
            
            if coingecko_results:
                html += f'''
                <div class="accordion-item">
                    <div class="accordion-summary" onclick="toggleSearchAccordion(this)">
                        <span>🦎 CoinGecko研究 ({len(coingecko_results)}项)</span>
                        <span class="accordion-icon">▼</span>
                    </div>
                    <div class="accordion-content">
                        <div class="accordion-inner">
                '''
                
                for result in coingecko_results:
                    request = result.get('request', {})
                    query = self._safe_format_value(request.get('query', ''))
                    purpose = self._safe_format_value(request.get('purpose', ''))
                    status = result.get('status', 'unknown')
                    
                    if status == 'success':
                        result_data = result.get('result', {})
                        html += f'''
                        <div class="coingecko-item">
                            <div class="coingecko-header">
                                <span class="coingecko-query">{query[:100]}...</span>
                                <span class="status-success">✅ 成功</span>
                            </div>
                            <div class="coingecko-purpose">{purpose}</div>
                        '''
                        
                        # 显示结果数据
                        if result_data.get('results'):
                            html += '<div class="coingecko-results">'
                            for r in result_data['results'][:3]:
                                html += f'<div class="result-item">{self._safe_format_value(r)}</div>'
                            html += '</div>'
                        
                        html += '</div>'
                    else:
                        error_msg = self._safe_format_value(result.get('result', {}).get('error', ''))
                        html += f'''
                        <div class="coingecko-item coingecko-failed">
                            <div class="coingecko-header">
                                <span class="coingecko-query">{query[:100]}...</span>
                                <span class="status-failed">❌ 失败</span>
                            </div>
                            <div class="coingecko-error">{error_msg}</div>
                        </div>
                        '''
                
                html += '''
                        </div>
                    </div>
                </div>
                '''
            
            # 5. 整体评估
            if results_analysis.get('overall_assessment'):
                overall_assessment = results_analysis['overall_assessment']
                html += f'''
                <div class="accordion-item">
                    <div class="accordion-summary" onclick="toggleSearchAccordion(this)">
                        <span>📊 整体评估</span>
                        <span class="accordion-icon">▼</span>
                    </div>
                    <div class="accordion-content">
                        <div class="accordion-inner">
                            <div class="assessment-grid">
                                <div class="assessment-card">
                                    <div class="assessment-value">{overall_assessment.get('support_level', 'N/A')}</div>
                                    <div class="assessment-label">支持度</div>
                                </div>
                                <div class="assessment-card">
                                    <div class="assessment-value">{overall_assessment.get('confidence_score', 'N/A')}</div>
                                    <div class="assessment-label">置信度</div>
                                </div>
                                <div class="assessment-card">
                                    <div class="assessment-value">{overall_assessment.get('reliability_rating', 'N/A')}</div>
                                    <div class="assessment-label">可靠性</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                '''
            
            # 6. 分析总结
            if results_analysis.get('analysis_summary'):
                analysis_summary = self._safe_format_value(results_analysis['analysis_summary'])
                html += f'''
                <div class="accordion-item">
                    <div class="accordion-summary" onclick="toggleSearchAccordion(this)">
                        <span>📝 分析总结</span>
                        <span class="accordion-icon">▼</span>
                    </div>
                    <div class="accordion-content">
                        <div class="accordion-inner">
                            <div class="summary-box">{analysis_summary}</div>
                        </div>
                    </div>
                </div>
                '''
            
            html += '</div>'  # 结束 search-results-accordion
            
            return html
            
        except Exception as e:
            self.logger.error(f"格式化完整搜索结果失败: {e}")
            return f'<div class="analysis-content">搜索结果格式化失败: {str(e)}</div>'
    
    def _format_verification_results_complete(self, prediction: Dict) -> str:
        """格式化真实验证结果 - 完整版"""
        try:
            real_verification = prediction.get('real_verification', {})
            
            html = '<div class="analysis-content">'
            
            if 'error' in real_verification:
                html += f'<p class="error">验证失败: {self._safe_format_value(real_verification["error"])}</p>'
            else:
                # 基准信息
                base_price = self._safe_format_value(real_verification.get('base_price', 0))
                base_date = self._safe_format_value(real_verification.get('base_date', 'N/A'))
                
                html += f'<p><strong>基准价格:</strong> ${base_price}</p>'
                html += f'<p><strong>基准时间:</strong> {base_date}</p>'
                
                # 验证结果网格
                html += '<div class="verification-grid">'
                check_points = real_verification.get('check_points', [])
                
                for cp in check_points:
                    try:
                        if isinstance(cp, dict) and cp.get('data_quality') == 'pending':
                            check_point = self._safe_format_value(cp.get('check_point', 'N/A'))
                            target_date = self._safe_format_value(cp.get('target_date', ''))
                            html += f'''
                            <div class="verification-item verification-pending">
                                <strong>{check_point}</strong><br>
                                待预测<br>
                                {target_date}
                            </div>
                            '''
                        elif isinstance(cp, dict) and 'is_correct' in cp:
                            is_correct = cp.get('is_correct', False)
                            css_class = 'verification-correct' if is_correct else 'verification-incorrect'
                            
                            check_point = self._safe_format_value(cp.get('check_point', 'N/A'))
                            target_price = self._safe_format_value(cp.get('target_price', 0))
                            price_change = self._safe_format_value(cp.get('price_change_percent', 0))
                            
                            html += f'''
                            <div class="verification-item {css_class}">
                                <strong>{check_point}</strong><br>
                                ${target_price}<br>
                                {price_change}%<br>
                                {'✅ 正确' if is_correct else '❌ 错误'}
                            </div>
                            '''
                        elif isinstance(cp, dict) and 'error' in cp:
                            html += f'''
                            <div class="verification-item verification-failed">
                                <strong>{self._safe_format_value(cp.get('check_point', 'N/A'))}</strong><br>
                                数据获取失败<br>
                                {self._safe_format_value(cp.get('error', 'Unknown error'))}
                            </div>
                            '''
                    except Exception as e:
                        html += f'<div class="verification-item verification-failed">检查点解析失败: {str(e)}</div>'
                
                html += '</div>'
                
                # 整体准确率
                overall_accuracy = self._safe_format_value(real_verification.get('overall_accuracy', 0))
                correct_count = self._safe_format_value(real_verification.get('correct_count', 0))
                total_count = self._safe_format_value(real_verification.get('total_count', 0))
                
                html += f'<h4>整体准确率: {overall_accuracy}%</h4>'
                html += f'<p>正确预测: {correct_count}/{total_count}</p>'
            
            html += '</div>'
            return html
            
        except Exception as e:
            self.logger.error(f"格式化验证结果失败: {e}")
            return f'<div class="analysis-content">验证结果格式化失败: {str(e)}</div>'
    
    def _format_comprehensive_analysis_complete(self, prediction: Dict) -> str:
        """格式化综合分析结果 - 完整版"""
        try:
            comprehensive = prediction.get('comprehensive_analysis', {})
            final_assessment = comprehensive.get('final_assessment', {})
            
            html = '<div class="analysis-content">'
            
            # 最终评估
            html += f'<h4>最终评估: {self._safe_format_value(final_assessment.get("overall_accuracy", "N/A"))}</h4>'
            
            # 评估质量
            quality = final_assessment.get('prediction_quality', {})
            if quality:
                html += '<p><strong>预测质量指标:</strong></p>'
                html += '<ul>'
                html += f'<li>具体性: {self._safe_format_value(quality.get("specificity", "N/A"))}</li>'
                html += f'<li>逻辑性: {self._safe_format_value(quality.get("logic_soundness", "N/A"))}</li>'
                html += f'<li>市场感知: {self._safe_format_value(quality.get("market_awareness", "N/A"))}</li>'
                html += f'<li>时机把握: {self._safe_format_value(quality.get("timing_precision", "N/A"))}</li>'
                html += '</ul>'
            
            # 详细评估
            detailed = comprehensive.get('detailed_evaluation', {})
            
            # 正确的方面
            if detailed.get('what_went_right'):
                html += '<h4>✅ 预测正确的方面</h4>'
                html += '<ul>'
                for item in detailed['what_went_right'][:3]:
                    try:
                        aspect = self._safe_format_value(item.get("aspect", ""))
                        explanation = self._safe_format_value(item.get("explanation", ""))
                        html += f'<li><strong>{aspect}:</strong> {explanation}</li>'
                    except:
                        html += f'<li>数据解析失败</li>'
                html += '</ul>'
            
            # 错误的方面
            if detailed.get('what_went_wrong'):
                html += '<h4>❌ 预测错误的方面</h4>'
                html += '<ul>'
                for item in detailed['what_went_wrong'][:3]:
                    try:
                        aspect = self._safe_format_value(item.get("aspect", ""))
                        explanation = self._safe_format_value(item.get("explanation", ""))
                        html += f'<li><strong>{aspect}:</strong> {explanation}</li>'
                    except:
                        html += f'<li>数据解析失败</li>'
                html += '</ul>'
            
            # 综合总结
            if comprehensive.get('comprehensive_summary'):
                html += '<div class="comprehensive-insights">'
                html += f'<h4>综合洞察</h4>'
                html += f'<p>{self._safe_format_value(comprehensive["comprehensive_summary"])}</p>'
                html += '</div>'
            
            html += '</div>'
            return html
        except Exception as e:
            self.logger.error(f"格式化综合分析失败: {e}")
            return f'<div class="analysis-content">综合分析格式化失败: {str(e)}</div>'

    # 翻译辅助方法
    def _translate_category(self, category: str) -> str:
        """翻译分类"""
        translations = {
            'technical_analysis': '📈 技术分析',
            'fundamental_analysis': '🔬 基本面分析', 
            'market_sentiment': '💭 市场情绪',
            'on_chain_data': '⛓️ 链上数据',
            'price_action': '💰 价格走势',
            'volume_analysis': '📊 成交量分析'
        }
        return translations.get(category, category)
    
    def _translate_impact(self, impact: str) -> str:
        """翻译影响"""
        translations = {
            'positive': '积极影响',
            'negative': '消极影响', 
            'neutral': '中性影响'
        }
        return translations.get(impact, impact)
    
    def _translate_evidence_type(self, type_str: str) -> str:
        """翻译证据类型"""
        translations = {
            'news_event': '📰 新闻事件',
            'fundamental_change': '🔄 基本面变化',
            'on_chain_metric': '⛓️ 链上指标',
            'market_data': '📊 市场数据',
            'policy_change': '🏛️ 政策变化'
        }
        return translations.get(type_str, type_str)
    
    def _translate_strength(self, strength: str) -> str:
        """翻译强度"""
        translations = {
            'strong': '强',
            'moderate': '中等',
            'weak': '弱',
            'unknown': '未知'
        }
        return translations.get(strength, strength)
    
    def _translate_relevance(self, relevance: str) -> str:
        """翻译相关性"""
        translations = {
            'relevant': '高度相关',
            'tangential': '间接相关',
            'irrelevant': '不相关'
        }
        return translations.get(relevance, relevance)
    
    def _translate_impact_level(self, impact: str) -> str:
        """翻译影响级别"""
        translations = {
            'significant': '重大影响',
            'moderate': '中等影响',
            'minor': '轻微影响',
            'unknown': '未知影响'
        }
        return translations.get(impact, impact)

    def generate_kol_list_html(self, kol_summaries: Dict) -> str:
        """生成KOL列表HTML"""
        try:
            # 准备KOL数据
            kol_data = {}
            for kol_name, summary in kol_summaries.items():
                avg_score = summary['total_score'] / summary['coin_count'] if summary['coin_count'] > 0 else 0
                avg_accuracy = summary['total_accuracy'] / summary['coin_count'] if summary['coin_count'] > 0 else 0
                
                kol_id = kol_name.lower().replace(' ', '_')
                
                # 直接使用已经在_collect_kol_summary中设置好的图片路径
                local_background = summary.get('local_background', '')
                local_avatar = summary.get('local_avatar', '')
                has_background = summary.get('has_background', False)
                has_avatar = summary.get('has_avatar', False)
                
                # 生成完整的背景和头像HTML
                background_style = self._generate_image_style(local_background)
                
                # 生成头像HTML
                if has_avatar and local_avatar:
                    avatar_html = f'<div class="kol-avatar" style="background-image: url(\'{local_avatar}\'); background-size: cover; background-position: center;"></div>'
                else:
                    avatar_html = f'<div class="kol-avatar default">{kol_name[:2].upper()}</div>'
                
                # 不在汇总数据中暴露数值评分，仅保留等级(tier)/评级用于展示
                # 计算KOL层面的tier：取该KOL所有币种中最优的tier
                tiers = [c.get('tier') for c in summary.get('coins', []) if c.get('tier')]
                tier_order = [
                    'S+', 'S', 'S-', 'A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-'
                ]
                best_tier = ''
                try:
                    tier_ranks = {t: i for i, t in enumerate(tier_order)}
                    ranked = sorted([t for t in tiers if t in tier_ranks], key=lambda x: tier_ranks[x])
                    best_tier = ranked[0] if ranked else ''
                except Exception:
                    best_tier = ''

                kol_data[kol_id] = {
                    'id': kol_id,
                    'name': kol_name,
                    'initials': kol_name[:2].upper(),
                    'tier': best_tier,
                    'overall_score': round(avg_score, 1),
                    'overall_accuracy': round(avg_accuracy, 1),
                    'overall_grade': self._calculate_grade(avg_score),
                    'investment_grade': self._calculate_investment_grade(avg_score),
                    'analyzed_coins': [c['coin_name'] for c in summary['coins']],
                    'short_term_accuracy': round(sum(c['short_term_accuracy'] for c in summary['coins']) / len(summary['coins']), 1) if summary['coins'] else 0,
                    'long_term_accuracy': round(sum(c['long_term_accuracy'] for c in summary['coins']) / len(summary['coins']), 1) if summary['coins'] else 0,
                    'key_verdict': self._generate_kol_verdict(kol_name, best_tier, avg_accuracy, summary['coin_count']),
                    'background_image_path': local_background,
                    'avatar_image_path': local_avatar,
                    'has_background': has_background,
                    'has_avatar': has_avatar,
                    'background_style': background_style,
                    'avatar_html': avatar_html
                }
            
            # 修改HTML模板
            html_content = self._get_kol_list_template_complete().replace('{kol_data_placeholder}', json.dumps(kol_data, ensure_ascii=False))
            
            # 保存文件
            filepath = os.path.join(self.output_dir, "index.html")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"✅ KOL列表报告生成: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"生成KOL列表HTML失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def generate_kol_coins_html(self, kol_name: str, summary: Dict) -> str:
        """生成KOL币种分析页面"""
        try:
            # 计算综合数据
            avg_score = summary['total_score'] / summary['coin_count'] if summary['coin_count'] > 0 else 0
            avg_accuracy = summary['total_accuracy'] / summary['coin_count'] if summary['coin_count'] > 0 else 0
            
            # 为子目录HTML生成正确的图片路径
            bg_filename = summary.get('background_filename', '')
            avatar_filename = summary.get('avatar_filename', '')
            has_background = summary.get('has_background', False)
            has_avatar = summary.get('has_avatar', False)
            
            local_background_sub = self._get_image_path(bg_filename, 'sub') if bg_filename else ''
            local_avatar_sub = self._get_image_path(avatar_filename, 'sub') if avatar_filename else ''
            
            # 生成完整的CSS样式和HTML
            background_style = self._generate_image_style(local_background_sub)
            
            # 生成头像HTML
            if has_avatar and local_avatar_sub:
                avatar_html = f'<div class="kol-avatar" style="background-image: url(\'{local_avatar_sub}\'); background-size: cover; background-position: center;"></div>'
            else:
                avatar_html = f'<div class="kol-avatar default">{kol_name[:2].upper()}</div>'
            
            # 准备模板数据
            template_data = {
                'kol_name': kol_name,
                'kol_initials': kol_name[:2].upper(),
                'grade': self._calculate_grade(avg_score),
                'tier': summary.get('tier', ''),
                'investment_grade': self._calculate_investment_grade(avg_score),
                'market_influence': self._calculate_market_influence(avg_score),
                'key_verdict': f"@{kol_name} 在加密货币分析领域表现{self._get_performance_desc(avg_score)}，"
                             f"共分析了 {summary['coin_count']} 个币种，整体准确率达到 {avg_accuracy:.1f}%。"
                             f"其分析风格{self._get_style_desc(avg_score)}，{self._get_recommendation(avg_score)}。",
                'professional_metrics': self._generate_metrics_html(summary),
                'competency_matrix': self._generate_competency_html(summary),
                'investment_advisory': self._generate_advisory_html(summary),
                'strengths_weaknesses': self._generate_strengths_html(summary),
                'forward_looking': self._generate_forward_html(summary),
                'coin_analysis_data_placeholder': json.dumps(summary['coins'], ensure_ascii=False),
                'background_style': background_style,
                'avatar_html': avatar_html
            }
            
            # 生成HTML
            html_content = self._get_kol_coins_template_complete()
            for key, value in template_data.items():
                html_content = html_content.replace(f'{{{key}}}', str(value))
            
            # 保存文件
            kol_id = kol_name.lower().replace(' ', '_')
            filename = f"{kol_id}_analysis.html"
            filepath = os.path.join(self.output_dir, "kol_reports", filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"✅ KOL币种报告生成: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"生成KOL币种HTML失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _calculate_time_span(self, analysis_result: Dict) -> str:
        """计算时间跨度 - 同时显示发布跨度和预测周期"""
        predictions = analysis_result.get('prediction_results', [])
        if not predictions:
            return 'N/A'

        # 1. 计算推文发布跨度
        dates = []
        for pred in predictions:
            if 'tweet_info' in pred:
                try:
                    dates.append(pd.to_datetime(pred['tweet_info']['tweet_created_at']))
                except:
                    continue

        if len(dates) == 0:
            return 'N/A'

        if len(dates) == 1:
            publish_span = '单次预测'
        else:
            span_days = (max(dates) - min(dates)).days
            if span_days == 0:
                publish_span = '同日发布'
            else:
                publish_span = f'{span_days}天'

        # 2. 计算预测验证的最长周期
        max_prediction_days = 0
        for pred in predictions:
            # 从intelligent_check_points获取最长的验证周期
            check_points = pred.get('intelligent_check_points', [])
            if check_points:
                for check_point in check_points:
                    # check_point格式如: "7d", "30d", "90d", "180d"
                    try:
                        if isinstance(check_point, str) and check_point.endswith('d'):
                            days = int(check_point[:-1])
                            max_prediction_days = max(max_prediction_days, days)
                    except:
                        continue

        # 3. 生成最终显示
        if max_prediction_days > 0:
            return f'发布{publish_span} | 预测周期最长{max_prediction_days}天'
        else:
            return f'发布{publish_span}'
    
    # 计算等级和分数的辅助方法
    def _calculate_grade(self, score: float) -> str:
        """计算评级"""
        if score >= 95: return 'S'
        elif score >= 90: return 'A+'
        elif score >= 85: return 'A'
        elif score >= 80: return 'A-'
        elif score >= 75: return 'B+'
        elif score >= 70: return 'B'
        elif score >= 65: return 'B-'
        elif score >= 60: return 'C+'
        elif score >= 55: return 'C'
        elif score >= 50: return 'C-'
        elif score >= 45: return 'D+'
        elif score >= 40: return 'D'
        else: return 'F'
    
    def _calculate_investment_grade(self, score: float) -> str:
        """计算投资等级"""
        if score >= 85: return 'INSTITUTIONAL'
        elif score >= 75: return 'PROFESSIONAL'
        elif score >= 60: return 'RETAIL'
        elif score >= 45: return 'CAUTIOUS'
        else: return 'AVOID'
    
    def _calculate_market_influence(self, score: float) -> str:
        """计算市场影响力"""
        if score >= 85: return '市场领袖'
        elif score >= 70: return '板块专家'
        elif score >= 55: return '活跃分析师'
        else: return '普通观察者'
    
    def _generate_kol_verdict(self, kol_name: str, tier: str, accuracy: float, coin_count: int) -> str:
        """生成KOL综合评价描述（同时考虑tier和准确率，避免过于苛刻）"""
        # 币种数量描述
        coin_desc = f"{coin_count} 个币种" if coin_count > 1 else "1 个币种"

        # 将tier转换为数值等级（用于判断）
        tier_order = ['S+', 'S', 'S-', 'A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-']
        tier_level = tier_order.index(tier) if tier in tier_order else 14  # 默认最低

        # 准确率等级
        if accuracy >= 80:
            acc_level = 'excellent'  # 优秀
            accuracy_comment = f"准确率高达 {accuracy:.1f}%"
        elif accuracy >= 70:
            acc_level = 'good'  # 良好
            accuracy_comment = f"准确率达到 {accuracy:.1f}%"
        elif accuracy >= 60:
            acc_level = 'fair'  # 尚可
            accuracy_comment = f"准确率为 {accuracy:.1f}%"
        elif accuracy >= 50:
            acc_level = 'moderate'  # 一般
            accuracy_comment = f"准确率为 {accuracy:.1f}%"
        elif accuracy >= 40:
            acc_level = 'low'  # 较低
            accuracy_comment = f"准确率仅 {accuracy:.1f}%"
        else:
            acc_level = 'poor'  # 差
            accuracy_comment = f"准确率低至 {accuracy:.1f}%"

        # 根据tier和准确率的组合，生成更合理的描述
        # tier好准确率也好 -> 正面评价
        # tier差但准确率好 -> 中性偏正面评价（等级不高但预测准）
        # tier好但准确率差 -> 中性偏负面评价（等级虚高）
        # tier差准确率也差 -> 负面评价

        if tier_level <= 2:  # S+, S, S-
            performance = "卓越表现"
            capability = "顶级的分析能力"
        elif tier_level <= 5:  # A+, A, A-
            performance = "优秀表现"
            capability = "专业的分析能力"
        elif tier_level <= 8:  # B+, B, B-
            if acc_level in ['excellent', 'good']:
                performance = "中等表现"
                capability = "可靠的预测准确性"
            else:
                performance = "中等表现"
                capability = "基础的分析能力"
        elif tier_level <= 11:  # C+, C, C-
            if acc_level in ['excellent', 'good']:
                performance = "等级一般但预测较准"
                capability = "尚可的分析水平"
            elif acc_level == 'fair':
                performance = "表现一般"
                capability = "有限的分析能力"
            else:
                performance = "表现较弱"
                capability = "欠缺的分析能力"
        else:  # D+, D, D-
            if acc_level in ['excellent', 'good']:
                # tier低但准确率高：温和评价
                performance = "等级较低但准确率尚可"
                capability = "分析能力有待提升"
            elif acc_level == 'fair':
                # tier低准确率也一般：中性评价
                performance = "表现不佳"
                capability = "分析能力需要改进"
            else:
                # tier低准确率也低：负面评价
                performance = "表现较差"
                capability = "分析能力明显不足"

        # 组合描述
        return f"@{kol_name} 在 {coin_desc} 分析中{performance}，{accuracy_comment}，展现了{capability}。"
    
    def _get_performance_desc(self, score: float) -> str:
        """获取表现描述（保留用于其他地方）"""
        if score >= 85: return '卓越'
        elif score >= 70: return '优秀'
        elif score >= 55: return '良好'
        elif score >= 40: return '一般'
        else: return '需要改进'
    
    def _get_capability_desc(self, score: float) -> str:
        """获取能力描述（保留用于其他地方）"""
        if score >= 85: return '专业级'
        elif score >= 70: return '熟练的'
        elif score >= 55: return '合格的'
        else: return '发展中的'
    
    def _get_style_desc(self, score: float) -> str:
        """获取风格描述"""
        if score >= 85: return '严谨专业，逻辑清晰'
        elif score >= 70: return '分析全面，观点明确'
        elif score >= 55: return '基础扎实，有待提升'
        else: return '需要加强系统性分析'
    
    def _get_recommendation(self, score: float) -> str:
        """获取推荐建议"""
        if score >= 85: return '强烈推荐关注其分析观点'
        elif score >= 70: return '值得参考其市场洞察'
        elif score >= 55: return '可以选择性参考'
        else: return '建议谨慎对待其观点'
    
    def _generate_metrics_html(self, summary: Dict) -> str:
        """生成专业指标HTML - 简化版本，只显示准确率和等级"""
        try:
            def safe_avg(total, count, default=0):
                if count > 0:
                    try:
                        return float(total) / float(count)
                    except (TypeError, ValueError, ZeroDivisionError):
                        return default
                return default

            coin_count = max(summary.get('coin_count', 0), 1)
            avg_accuracy = safe_avg(summary.get('total_accuracy', 0), coin_count)

            tier_display = summary.get('tier', '') or '-'

            # 根据准确率确定颜色和图标
            if avg_accuracy >= 80:
                accuracy_class = 'metric-excellent'
                accuracy_icon = '🌟'
            elif avg_accuracy >= 70:
                accuracy_class = 'metric-good'
                accuracy_icon = '✨'
            elif avg_accuracy >= 60:
                accuracy_class = 'metric-average'
                accuracy_icon = '⭐'
            else:
                accuracy_class = 'metric-poor'
                accuracy_icon = '📊'

            return f'''
            <div class="professional-metrics-enhanced">
                <div class="metric-card-large {accuracy_class}">
                    <div class="metric-icon">{accuracy_icon}</div>
                    <div class="metric-content">
                        <div class="metric-value-large">{avg_accuracy:.1f}%</div>
                        <div class="metric-label-large">平均准确率</div>
                        <div class="metric-progress">
                            <div class="metric-progress-bar" style="width: {avg_accuracy}%"></div>
                        </div>
                    </div>
                </div>
                <div class="metric-card-large metric-tier">
                    <div class="metric-icon">🏆</div>
                    <div class="metric-content">
                        <div class="metric-value-large">{tier_display}</div>
                        <div class="metric-label-large">综合等级</div>
                        <div class="metric-subtitle">基于{coin_count}个币种的分析</div>
                    </div>
                </div>
            </div>
            '''
        except Exception as e:
            self.logger.error(f"生成指标HTML失败: {e}")
            return '<div class="professional-metrics-enhanced">指标加载失败</div>'
    
    # 其他辅助HTML生成方法保持原样...
    def _generate_competency_html(self, summary: Dict) -> str:
        """生成专业能力矩阵HTML"""
        avg_score = summary['total_score'] / summary['coin_count'] if summary['coin_count'] > 0 else 0
        
        # 基于平均分数计算各项能力
        tech_score = min(100, max(30, avg_score * 0.9 + 10))
        fund_score = min(100, max(30, avg_score * 0.85 + 15))
        psych_score = min(100, max(40, avg_score * 0.95 + 5))
        risk_score = min(100, max(35, avg_score * 0.75 + 25))
        comm_score = min(100, max(50, avg_score * 0.8 + 20))
        
        return f'''
        <div class="competency-matrix">
            <div class="competency-card">
                <div class="competency-title">技术分析能力</div>
                <div class="competency-score {self._get_score_class(tech_score)}">{tech_score:.0f}</div>
                <div class="progress-bar">
                    <div class="progress-fill" data-width="{tech_score}" style="width: 0%"></div>
                </div>
                <p>图表分析、技术指标运用{self._get_ability_desc(tech_score)}</p>
            </div>
            
            <div class="competency-card">
                <div class="competency-title">基本面分析</div>
                <div class="competency-score {self._get_score_class(fund_score)}">{fund_score:.0f}</div>
                <div class="progress-bar">
                    <div class="progress-fill" data-width="{fund_score}" style="width: 0%"></div>
                </div>
                <p>项目研究、价值发现能力{self._get_ability_desc(fund_score)}</p>
            </div>
            
            <div class="competency-card">
                <div class="competency-title">市场心理把握</div>
                <div class="competency-score {self._get_score_class(psych_score)}">{psych_score:.0f}</div>
                <div class="progress-bar">
                    <div class="progress-fill" data-width="{psych_score}" style="width: 0%"></div>
                </div>
                <p>情绪感知、趋势判断{self._get_ability_desc(psych_score)}</p>
            </div>
            
            <div class="competency-card">
                <div class="competency-title">风险管理</div>
                <div class="competency-score {self._get_score_class(risk_score)}">{risk_score:.0f}</div>
                <div class="progress-bar">
                    <div class="progress-fill" data-width="{risk_score}" style="width: 0%"></div>
                </div>
                <p>风险意识、仓位管理建议{self._get_ability_desc(risk_score)}</p>
            </div>
            
            <div class="competency-card">
                <div class="competency-title">沟通表达</div>
                <div class="competency-score {self._get_score_class(comm_score)}">{comm_score:.0f}</div>
                <div class="progress-bar">
                    <div class="progress-fill" data-width="{comm_score}" style="width: 0%"></div>
                </div>
                <p>观点清晰度、可执行性{self._get_ability_desc(comm_score)}</p>
            </div>
        </div>
        '''
    
    def _get_score_class(self, score: float) -> str:
        """获取分数CSS类"""
        if score >= 80: return 'score-excellent'
        elif score >= 60: return 'score-good'
        elif score >= 40: return 'score-average'
        else: return 'score-poor'
    
    def _get_ability_desc(self, score: float) -> str:
        """获取能力描述"""
        if score >= 80: return '表现优异'
        elif score >= 60: return '表现良好'
        elif score >= 40: return '有待提升'
        else: return '需要改进'
    
    # 其他生成方法简化版本...
    def _generate_advisory_html(self, summary: Dict) -> str:
        """生成投资建议HTML（简化版）"""
        return '''<div class="investment-advisory">
            <div class="advisory-title">投资建议将基于综合评估生成</div>
        </div>'''
    
    def _generate_strengths_html(self, summary: Dict) -> str:
        """生成优势劣势HTML（简化版）"""
        return '''<div class="strengths-weaknesses">
            <div class="strength-card">
                <h3>💪 核心优势</h3>
                <ul><li>分析能力持续稳定</li></ul>
            </div>
            <div class="weakness-card">
                <h3>⚠️ 改进领域</h3>
                <ul><li>可进一步提升预测准确率</li></ul>
            </div>
        </div>'''
    
    def _generate_forward_html(self, summary: Dict) -> str:
        """生成前瞻评估HTML（简化版）"""
        return '''<div class="forward-looking-section">
            <h3>🔮 未来发展潜力</h3>
            <p>基于当前表现，该KOL具备持续成长的潜力。</p>
        </div>'''
    
    def _get_default_template(self, template_name: str) -> str:
        """获取默认模板"""
        if template_name == 'kol_list':
            return self._get_kol_list_template_complete()
        elif template_name == 'kol_coins':
            return self._get_kol_coins_template_complete()
        else:
            return self._get_coin_analysis_template_complete()

    def _get_coin_analysis_template_complete(self) -> str:
        """获取完整的币种分析HTML模板"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@{kol_name} × {coin_name} 推理链分析</title>
    <style>
        body {
            font-family: 'Segoe UI', 'Microsoft YaHei', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6; margin: 0; padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; color: #333;
        }
        .container {
            max-width: 1800px; margin: 0 auto; background: white;
            border-radius: 20px; box-shadow: 0 15px 50px rgba(0,0,0,0.25);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 50px; text-align: center;
            position: relative;
        }
        .navigation {
            position: absolute; top: 20px; left: 20px;
            display: flex; gap: 10px;
        }
        .nav-btn {
            background: rgba(255,255,255,0.2); color: white;
            padding: 10px 20px; border-radius: 25px; text-decoration: none;
            font-weight: bold; backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        .nav-btn:hover {
            background: rgba(255,255,255,0.3);
            transform: translateX(-5px);
        }
        .header h1 { font-size: 3em; margin-bottom: 15px; font-weight: 700; }
        .subtitle { font-size: 1.4em; opacity: 0.9; margin-bottom: 30px; }
        
        .coin-summary {
            background: rgba(255,255,255,0.1); margin: 30px 0; 
            padding: 25px; border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.2);
        }
        .summary-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px; margin-top: 20px;
        }
        .summary-item {
            text-align: center;
        }
        .summary-label {
            font-size: 0.9em; opacity: 0.8; margin-bottom: 5px;
        }
        .summary-value {
            font-size: 1.8em; font-weight: bold;
        }
        
        .section {
            padding: 50px;
        }
        .section-title {
            font-size: 2.2em; margin-bottom: 30px; color: #333; 
            border-bottom: 3px solid #667eea; padding-bottom: 15px;
        }
        
        .chart-container {
            position: relative; text-align: center; margin: 40px 0;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); 
            border-radius: 20px; padding: 40px; box-shadow: inset 0 5px 15px rgba(0,0,0,0.1);
        }
        .chart-title {
            font-size: 1.6em; margin-bottom: 25px; font-weight: bold; 
            color: #333; text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
        }
        .chart-wrapper {
            position: relative; display: inline-block;
            border-radius: 15px; overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 1200px;
        }
        .chart-image { 
            width: 100%; 
            height: auto; 
            display: block;
            max-height: 600px;
            object-fit: contain;
        }
        
        /* CSS Hotpoint - 精确定位 */
        .chart-hotpoint {
            position: absolute;
            width: 28px;
            height: 28px;
            cursor: pointer;
            z-index: 100;
            transform: translate(-50%, -50%);
            transition: all 0.3s ease;
        }
        
        .chart-hotpoint:hover {
            transform: translate(-50%, -50%) scale(1.2);
            z-index: 200;
        }
        
        .chart-hotpoint.active {
            transform: translate(-50%, -50%) scale(1.3);
            z-index: 200;
            filter: drop-shadow(0 0 10px rgba(0, 123, 255, 0.8));
        }
        
        .chart-hotpoint svg {
            width: 100%;
            height: 100%;
            filter: drop-shadow(0 3px 8px rgba(0,0,0,0.4));
        }
        
        /* 固定悬浮面板 - 右侧位置 */
        .fixed-floating-panel {
            position: fixed;
            top: 10vh;
            right: 2vw;
            width: 400px;
            max-height: 80vh;
            background: white;
            border-radius: 15px;
            box-shadow: 0 15px 50px rgba(0,0,0,0.25);
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transform: translateX(100%);
            transition: all 0.4s ease;
            border: 2px solid #e9ecef;
            overflow: hidden;
        }
        
        .fixed-floating-panel.show {
            opacity: 1;
            visibility: visible;
            transform: translateX(0);
        }
        
        /* 面板头部 - 包含小图表 */
        .panel-header {
            background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
            color: white;
            padding: 0;
            margin: 0;
            position: relative;
        }
        
        .panel-title-section {
            padding: 15px 20px 10px 20px;
        }
        
        .panel-title {
            font-size: 1.1em;
            font-weight: bold;
            margin: 0 0 5px 0;
        }
        
        .panel-subtitle {
            font-size: 0.85em;
            opacity: 0.9;
            margin: 0;
        }
        
        /* 小型验证图表区域 */
        .mini-chart-container {
            height: 120px;
            background: rgba(255,255,255,0.1);
            margin: 10px;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
        }
        
        .mini-chart-canvas {
            width: 100%;
            height: 100%;
            display: block;
        }
        
        .close-panel-btn {
            position: absolute;
            top: 15px;
            right: 15px;
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
        }
        
        .close-panel-btn:hover {
            background: rgba(255,255,255,0.3);
        }
        
        /* 面板内容 */
        .panel-content {
            padding: 20px;
            max-height: calc(80vh - 200px);
            overflow-y: auto;
        }
        
        /* 预测详情卡片 */
        .prediction-details {
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .detail-section {
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #e9ecef;
        }
        
        .detail-section:last-child {
            border-bottom: none;
            margin-bottom: 0;
        }
        
        .section-title-small {
            font-size: 1.0em;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .detail-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 6px 0;
            padding: 5px 0;
        }
        
        .detail-label {
            color: #666;
            font-size: 0.85em;
            font-weight: 500;
        }
        
        .detail-value {
            color: #333;
            font-weight: bold;
            text-align: right;
            font-size: 0.9em;
        }
        
        .sentiment-badge {
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 0.75em;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .sentiment-bullish {
            background: #d4edda;
            color: #155724;
        }
        
        .sentiment-bearish {
            background: #f8d7da;
            color: #721c24;
        }
        
        .sentiment-neutral {
            background: #fff3cd;
            color: #856404;
        }
        
        .accuracy-meter {
            width: 100%;
            height: 6px;
            background: #e9ecef;
            border-radius: 3px;
            overflow: hidden;
            margin: 5px 0;
        }
        
        .accuracy-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 0.8s ease;
        }
        
        .accuracy-excellent { background: #28a745; }
        .accuracy-good { background: #17a2b8; }
        .accuracy-average { background: #ffc107; }
        .accuracy-poor { background: #dc3545; }
        
        /* 预测内容 */
        .prediction-content {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px;
            margin: 8px 0;
            font-style: italic;
            line-height: 1.4;
            border-left: 4px solid #007bff;
            font-size: 0.9em;
        }
        
        /* 验证结果网格 */
        .verification-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin: 8px 0;
        }
        
        .verification-item {
            background: #f8f9fa;
            padding: 8px;
            border-radius: 6px;
            text-align: center;
            font-size: 0.8em;
        }
        
        .verification-correct {
            background: #d4edda;
            color: #155724;
        }
        
        .verification-incorrect {
            background: #f8d7da;
            color: #721c24;
        }

        .verification-pending {
            background: #fff3cd;
            color: #856404;
        }

        .verification-failed {
            background: #e2e3e5;
            color: #383d41;
        }
        
        /* 搜索结果手风琴样式 - 完整版 */
        .search-results-accordion {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
        }
        
        .accordion-item {
            background: white;
            border-radius: 8px;
            margin-bottom: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            overflow: hidden;
        }
        
        .accordion-summary {
            background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
            color: white;
            padding: 12px 15px;
            cursor: pointer;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s ease;
        }
        
        .accordion-summary:hover {
            background: linear-gradient(135deg, #0056b3 0%, #004085 100%);
        }
        
        .accordion-icon {
            transition: transform 0.3s ease;
        }
        
        .accordion-item.open .accordion-icon {
            transform: rotate(180deg);
        }
        
        .accordion-content {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
            background: white;
        }
        
        .accordion-item.open .accordion-content {
            max-height: 1000px;
        }
        
        .accordion-inner {
            padding: 15px;
        }
        
        /* 洞察项目样式 */
        .insight-item {
            background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #ff9800;
            margin-bottom: 15px;
        }
        
        .insight-category {
            font-weight: bold;
            color: #ef6c00;
            font-size: 0.9em;
            margin-bottom: 8px;
            padding: 2px 8px;
            background: rgba(239, 108, 0, 0.1);
            border-radius: 12px;
            display: inline-block;
        }
        
        .insight-content {
            color: #333;
            line-height: 1.5;
            margin-bottom: 10px;
        }
        
        .supporting-data {
            background: rgba(0,0,0,0.05);
            padding: 10px;
            border-radius: 6px;
            font-size: 0.85em;
            color: #666;
            margin-bottom: 8px;
        }
        
        .score-badge {
            background: linear-gradient(135deg, #2196F3, #1976D2);
            color: white;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
        }
        
        .impact-badge {
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
        }
        
        .impact-positive { background: #d4edda; color: #155724; }
        .impact-negative { background: #f8d7da; color: #721c24; }
        .impact-neutral { background: #fff3cd; color: #856404; }
        
        .evidence-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #4caf50;
            margin-bottom: 12px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }
        
        .evidence-negative {
            border-left-color: #f44336;
            background: linear-gradient(135deg, #fce4ec 0%, #f8bbd9 100%);
        }
        
        .evidence-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .evidence-type {
            background: #e3f2fd;
            color: #1565C0;
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 0.8em;
            font-weight: bold;
        }
        
        .evidence-strength {
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 0.75em;
            font-weight: bold;
        }
        
        .strength-strong { background: #d4edda; color: #155724; }
        .strength-moderate { background: #fff3cd; color: #856404; }
        .strength-weak { background: #f8d7da; color: #721c24; }
        .strength-unknown { background: #e9ecef; color: #6c757d; }
        
        .evidence-impact {
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 0.75em;
            font-weight: bold;
        }
        
        .impact-significant { background: #f8d7da; color: #721c24; }
        .impact-moderate { background: #fff3cd; color: #856404; }
        .impact-minor { background: #d4edda; color: #155724; }
        .impact-unknown { background: #e9ecef; color: #6c757d; }
        
        .evidence-description {
            color: #333;
            line-height: 1.4;
            margin-bottom: 6px;
        }
        
        .evidence-relevance {
            color: #666;
            font-size: 0.85em;
            font-style: italic;
        }
        
        .assessment-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-top: 12px;
        }
        
        .assessment-card {
            background: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
            text-align: center;
            border-top: 3px solid #007bff;
        }
        
        .assessment-value {
            font-size: 1.3em;
            font-weight: bold;
            color: #007bff;
            margin-bottom: 4px;
        }
        
        .assessment-label {
            color: #666;
            font-size: 0.85em;
        }
        
        .summary-box {
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            padding: 15px;
            border-radius: 8px;
            border-left: 5px solid #2196F3;
            font-size: 0.9em;
            line-height: 1.5;
        }
        
        /* CoinGecko研究样式 */
        .coingecko-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #8bc34a;
            margin-bottom: 12px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }
        
        .coingecko-failed {
            border-left-color: #f44336;
            background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        }
        
        .coingecko-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .coingecko-query {
            font-weight: bold;
            color: #333;
            flex: 1;
            margin-right: 10px;
        }
        
        .status-success {
            color: #4caf50;
            font-size: 0.9em;
            font-weight: bold;
        }
        
        .status-failed {
            color: #f44336;
            font-size: 0.9em;
            font-weight: bold;
        }
        
        .coingecko-purpose {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
            font-style: italic;
        }
        
        .coingecko-results {
            background: rgba(0,0,0,0.05);
            padding: 10px;
            border-radius: 6px;
        }
        
        .result-item {
            background: white;
            padding: 8px;
            border-radius: 4px;
            margin-bottom: 5px;
            font-size: 0.85em;
            border-left: 3px solid #8bc34a;
        }
        
        .coingecko-error {
            color: #f44336;
            font-size: 0.9em;
            background: rgba(244, 67, 54, 0.1);
            padding: 8px;
            border-radius: 4px;
        }
        
        .chart-legend {
            margin-top: 30px; padding: 25px; 
            background: rgba(102, 126, 234, 0.1); border-radius: 15px;
        }
        .legend-title {
            font-size: 1.1em; font-weight: bold; margin-bottom: 20px; color: #333;
        }
        .legend-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 15px; margin-bottom: 15px;
        }
        .legend-item {
            color: #666; font-size: 0.95em; padding: 8px;
            background: white; border-radius: 8px; text-align: center;
        }
        .legend-note {
            color: #666; font-size: 0.95em; text-align: center; 
            background: white; padding: 12px; border-radius: 8px; margin-top: 15px;
        }
        
        /* 推文详情样式 */
        .tweet-detail-card {
            background: white; border-radius: 20px; padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15); margin: 25px 0;
            border-left: 6px solid #2196F3;
            transition: all 0.4s ease;
        }
        .tweet-detail-card:hover {
            transform: translateY(-3px); 
            box-shadow: 0 15px 35px rgba(0,0,0,0.2);
        }
        
        .tweet-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 20px; border-bottom: 2px solid #eee; padding-bottom: 15px;
        }
        .tweet-title {
            font-size: 1.4em; font-weight: bold; color: #333;
        }
        .tweet-meta {
            color: #666; font-size: 0.95em; margin-top: 5px;
        }
        
        .expand-arrow {
            font-size: 2em; 
            color: #2196F3; 
            font-weight: bold;
            cursor: pointer;
            user-select: none;
            padding: 10px;
            margin: -10px;
            border-radius: 10px;
            transition: all 0.3s ease;
        }
        .expand-arrow:hover {
            background: rgba(33, 150, 243, 0.1);
            transform: scale(1.1);
        }
        
        .tweet-content {
            margin: 20px 0; padding: 20px; background: #f8f9fa;
            border-radius: 12px; font-style: italic; color: #555;
            border-left: 4px solid #007bff;
        }
        
        .analysis-section {
            margin: 25px 0; padding: 20px; border-radius: 12px;
        }
        .ai-analysis { background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); }
        .search-results { background: linear-gradient(135deg, #fff3e0 0%, #ffcc80 100%); }
        .verification-results { background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c8 100%); }
        .comprehensive-analysis { background: linear-gradient(135deg, #fce4ec 0%, #f8bbd9 100%); }
        
        .analysis-title {
            font-size: 1.3em; font-weight: bold; margin-bottom: 15px;
            display: flex; align-items: center; gap: 10px;
        }
        
        .collapsible-content {
            max-height: 0; overflow: hidden; 
            transition: max-height 0.5s ease;
        }
        .collapsible-content.active {
            max-height: 5000px;
        }
        
        /* 响应式设计 */
        @media (max-width: 1200px) {
            .fixed-floating-panel {
                right: 1vw;
                width: 350px;
            }
        }
        
        @media (max-width: 768px) {
            .container { margin: 10px; }
            .section { padding: 25px; }
            .header h1 { font-size: 2em; }
            .summary-grid { grid-template-columns: 1fr 1fr; }
            .legend-grid { grid-template-columns: 1fr; }
            
            .fixed-floating-panel {
                position: fixed;
                top: auto;
                bottom: 0;
                left: 0;
                right: 0;
                width: auto;
                max-height: 60vh;
                border-radius: 15px 15px 0 0;
                transform: translateY(100%);
            }
            
            .fixed-floating-panel.show {
                transform: translateY(0);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header Section -->
        <div class="header">
            <div class="navigation">
                <a href="../index.html" class="nav-btn">← KOL列表</a>
                <a href="../kol_reports/{kol_id}_analysis.html" class="nav-btn">← {kol_name}币种列表</a>
                {coingecko_link_html}
            </div>
            
            <h1>@{kol_name} × {coin_name}</h1>
            <div class="subtitle">币种推理链详细分析</div>
            
            <div class="coin-summary">
                <h3 style="margin-top: 0;">📊 币种分析摘要</h3>
                <div class="summary-grid">
                    <div class="summary-item">
                        <div class="summary-label">预测数量</div>
                        <div class="summary-value">{total_predictions}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">准确率</div>
                        <div class="summary-value">{accuracy}%</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">时间跨度</div>
                        <div class="summary-value">{time_span}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">表现评级</div>
                        <div class="summary-value">{performance_grade}</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Chart Section -->
        <div class="section">
            <h2 class="section-title">📈 推理链价格走势与综合分析</h2>
            <div class="chart-container">
                <div class="chart-title">
                    {coin_name} 价格走势与预测点专业分析 (点击预测点查看详情)
                </div>
                <div class="chart-wrapper" id="chartWrapper">
                    {chart_html}
                </div>
                <div class="chart-legend">
                    <div class="legend-title">💡 专业级图表说明</div>
                    <div class="legend-grid">
                        <div class="legend-item">⭐ 深绿色：优秀预测 (≥80%准确率)</div>
                        <div class="legend-item">✓ 绿色：良好预测 (70-79%准确率)</div>
                        <div class="legend-item">~ 橙色：一般预测 (60-69%准确率)</div>
                        <div class="legend-item">✗ 红色：较差预测 (<60%准确率)</div>
                        <div class="legend-item">↗ 看涨预测 | ↘ 看跌预测 | → 中性预测</div>
                        <div class="legend-item">ST/MT/LT：短期/中期/长期预测</div>
                    </div>
                    <div class="legend-note">
                        点击图表上的预测点，右侧将显示详细分析和验证图表。验证图表展示预测前后5天的价格走势。
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Detailed Tweet Analysis -->
        <div class="section">
            <h2 class="section-title">📱 推文专业级详细分析</h2>
            <div style="margin-bottom: 25px; padding: 20px; background: #e3f2fd; border-radius: 12px;">
                <p style="color: #1565c0; margin: 0; font-weight: 500;">
                    点击箭头图标展开查看完整的专业分析，包括AI深度分析、搜索结果、真实验证数据、综合评估等。
                </p>
            </div>
            {tweet_details}
        </div>
    </div>
    
    <!-- 固定悬浮面板 -->
    <div class="fixed-floating-panel" id="fixedFloatingPanel">
        <div class="panel-header">
            <button class="close-panel-btn" onclick="hidePredictionPanel()">×</button>
            <div class="panel-title-section">
                <div class="panel-title" id="panelTitle">📊 预测详情分析</div>
                <div class="panel-subtitle" id="panelSubtitle">验证结果可视化</div>
            </div>
            
            <!-- 小型验证图表 -->
            <div class="mini-chart-container">
                <canvas class="mini-chart-canvas" id="miniChart"></canvas>
            </div>
        </div>
        
        <div class="panel-content" id="panelContent">
            <!-- 内容将动态填充 -->
        </div>
    </div>
    
    <script>
        // 全局变量
        const predictionData = {prediction_data_js};
        const priceData = {price_data_js};
        let hotpoints = [];
        let selectedHotpoint = null;
        let miniCanvas, miniCtx;
        
        // 初始化
        document.addEventListener('DOMContentLoaded', () => {
            setupMiniCanvas();
            initChartInteractions();
        });
        
        // 设置小型Canvas
        function setupMiniCanvas() {
            miniCanvas = document.getElementById('miniChart');
            if (!miniCanvas) return;
            
            miniCtx = miniCanvas.getContext('2d');
            
            const rect = miniCanvas.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            
            miniCanvas.width = rect.width * dpr;
            miniCanvas.height = rect.height * dpr;
            miniCtx.scale(dpr, dpr);
        }
        
        // 绘制验证小图表
        function drawMiniChart(prediction) {
            if (!miniCanvas || !miniCtx) return;
            
            const rect = miniCanvas.getBoundingClientRect();
            const width = rect.width;
            const height = rect.height;
            const padding = 15;
            
            miniCtx.clearRect(0, 0, width, height);
            
            const chartWidth = width - padding * 2;
            const chartHeight = height - padding * 2;
            
            // 获取预测点前后的数据
            const centerIndex = prediction.index || 0;
            
            // 修改：确定数据范围 - 验证时间前五天到最晚验证结果后五天
            // 获取验证时间点和最晚验证结果时间点
            const verificationTimepoints = [];
            if (prediction.verification_timepoints && Array.isArray(prediction.verification_timepoints)) {
                verificationTimepoints.push(...prediction.verification_timepoints);
            } else if (prediction.check_points && Array.isArray(prediction.check_points)) {
                verificationTimepoints.push(...prediction.check_points.map(cp => cp.timeIndex || centerIndex));
            }
            
            // 如果没有验证时间点，使用默认范围（前后5天）
            let startIndex = Math.max(0, centerIndex - 5);
            let endIndex = Math.min(priceData.length - 1, centerIndex + 5);
            
            // 如果有验证时间点，调整范围
            if (verificationTimepoints.length > 0) {
                const earliestVerification = Math.min(...verificationTimepoints);
                const latestVerification = Math.max(...verificationTimepoints);
                
                // 验证时间前五天到最晚验证结果后五天
                startIndex = Math.max(0, earliestVerification - 5);
                endIndex = Math.min(priceData.length - 1, latestVerification + 5);
            }
            
            const miniData = priceData.slice(startIndex, endIndex + 1);
            const predictionPointIndex = centerIndex - startIndex;
            
            if (miniData.length === 0) return;
            
            const prices = miniData.map(d => d.price);
            const minPrice = Math.min(...prices);
            const maxPrice = Math.max(...prices);
            const priceRange = maxPrice - minPrice || 1;
            
            // 绘制背景
            miniCtx.fillStyle = 'rgba(255,255,255,0.1)';
            miniCtx.fillRect(0, 0, width, height);
            
            // 绘制价格线
            miniCtx.strokeStyle = '#ffffff';
            miniCtx.lineWidth = 2;
            miniCtx.beginPath();
            
            miniData.forEach((point, index) => {
                const x = padding + (index / (miniData.length - 1)) * chartWidth;
                // 修改：移除1-计算，这样y轴坐标就会从下到上增长，符合价格图表惯例
                const y = padding + chartHeight - ((point.price - minPrice) / priceRange) * chartHeight;
                
                if (index === 0) {
                    miniCtx.moveTo(x, y);
                } else {
                    miniCtx.lineTo(x, y);
                }
            });
            
            miniCtx.stroke();
            
            // 标记预测点
            if (predictionPointIndex >= 0 && predictionPointIndex < miniData.length) {
                const predX = padding + (predictionPointIndex / (miniData.length - 1)) * chartWidth;
                // 修改：预测点的y坐标也需要调整计算方式
                const predY = padding + chartHeight - ((miniData[predictionPointIndex].price - minPrice) / priceRange) * chartHeight;
                
                // 预测点标记
                miniCtx.fillStyle = '#FFD700';
                miniCtx.beginPath();
                miniCtx.arc(predX, predY, 4, 0, 2 * Math.PI);
                miniCtx.fill();
                
                // 预测点边框
                miniCtx.strokeStyle = '#ffffff';
                miniCtx.lineWidth = 2;
                miniCtx.stroke();
                
                // 垂直参考线
                miniCtx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
                miniCtx.lineWidth = 1;
                miniCtx.setLineDash([3, 3]);
                miniCtx.beginPath();
                miniCtx.moveTo(predX, padding);
                miniCtx.lineTo(predX, height - padding);
                miniCtx.stroke();
                miniCtx.setLineDash([]);
            }
            
            // 标记验证时间点
            verificationTimepoints.forEach(timeIndex => {
                const verificationIndex = timeIndex - startIndex;
                if (verificationIndex >= 0 && verificationIndex < miniData.length) {
                    const verX = padding + (verificationIndex / (miniData.length - 1)) * chartWidth;
                    const verY = padding + chartHeight - ((miniData[verificationIndex].price - minPrice) / priceRange) * chartHeight;
                    
                    // 验证点标记
                    miniCtx.fillStyle = '#4CAF50';
                    miniCtx.beginPath();
                    miniCtx.arc(verX, verY, 3, 0, 2 * Math.PI);
                    miniCtx.fill();
                }
            });
            
            // 添加时间标签
            miniCtx.fillStyle = 'rgba(255, 255, 255, 0.8)';
            miniCtx.font = '10px Arial';
            miniCtx.textAlign = 'center';
            
            // 修改标签文本，显示相对天数
            miniCtx.fillText(`-${centerIndex - startIndex}d`, padding, height - 5);
            if (predictionPointIndex >= 0 && predictionPointIndex < miniData.length) {
                const predX = padding + (predictionPointIndex / (miniData.length - 1)) * chartWidth;
                miniCtx.fillText('预测', predX, height - 5);
            }
            miniCtx.fillText(`+${endIndex - centerIndex}d`, width - padding, height - 5);
            
            // 添加价格范围标签 - 修改位置：minPrice现在在底部，maxPrice在顶部
            miniCtx.textAlign = 'right';
            miniCtx.fillText('$' + maxPrice.toFixed(0), width - 5, padding + 10);
            miniCtx.fillText('$' + minPrice.toFixed(0), width - 5, height - padding - 5);
        }
        
        function toggleTweetDetail(index) {
            const content = document.getElementById('detail-' + index);
            const arrow = document.getElementById('arrow-' + index);
            content.classList.toggle('active');
            arrow.textContent = content.classList.contains('active') ? '▲' : '▼';
        }
        
        // 搜索结果手风琴切换
        function toggleSearchAccordion(element) {
            const accordionItem = element.parentElement;
            const isOpen = accordionItem.classList.contains('open');
            
            // 可以同时打开多个accordion
            if (isOpen) {
                accordionItem.classList.remove('open');
            } else {
                accordionItem.classList.add('open');
            }
        }
        
        // 精确计算坐标 - 基于图片尺寸
        function calculatePreciseCoordinates(pred, imgRect) {
            const relativeX = pred.relative_x || 0.5;
            const relativeY = pred.relative_y || 0.5;
            
            const percentX = Math.max(5, Math.min(95, relativeX * 100));
            const percentY = Math.max(5, Math.min(95, relativeY * 100));
            
            return {
                percentX,
                percentY,
                pixelX: imgRect.width * relativeX,
                pixelY: imgRect.height * relativeY
            };
        }
        
        // 添加CSS hotpoint
        function addCSSHotpoint(prediction, index) {
            const wrapper = document.getElementById('chartWrapper');
            const img = document.getElementById('priceChartImg');
            if (!wrapper || !img) return;
            
            const imgRect = img.getBoundingClientRect();
            const coords = calculatePreciseCoordinates(prediction, imgRect);
            
            // 根据准确率确定颜色
            const getColorByAccuracy = (accuracy) => {
                if (accuracy >= 80) return '#28a745';
                if (accuracy >= 70) return '#4CAF50';
                if (accuracy >= 60) return '#ffc107';
                return '#dc3545';
            };
            
            const accuracy = prediction.verification_accuracy || 0;
            const color = getColorByAccuracy(accuracy);
            
            const shapes = {
                'bullish': `<polygon points="14,3 26,23 2,23" fill="${color}" stroke="white" stroke-width="2"/>`,
                'bearish': `<polygon points="14,25 26,5 2,5" fill="${color}" stroke="white" stroke-width="2"/>`,
                'neutral': `<circle cx="14" cy="14" r="11" fill="${color}" stroke="white" stroke-width="2"/>`
            };
            
            const sentiment = prediction.sentiment || 'bullish';
            
            const hotpoint = document.createElement('div');
            hotpoint.className = 'chart-hotpoint';
            hotpoint.style.left = `${coords.percentX}%`;
            hotpoint.style.top = `${coords.percentY}%`;
            
            hotpoint.innerHTML = `
                <svg viewBox="0 0 28 28">
                    ${shapes[sentiment]}
                    <text x="14" y="18" text-anchor="middle" fill="white" 
                        font-size="9" font-weight="bold" 
                        font-family="'Liberation Sans', 'Cantarell', 'DejaVu Sans', Arial, sans-serif">
                        ${index + 1}
                    </text>
                </svg>
            `;
            
            // 点击事件 - 显示固定悬浮面板
            hotpoint.addEventListener('click', (e) => {
                e.stopPropagation();
                selectHotpoint(prediction, index);
                
                // 更新活动状态
                document.querySelectorAll('.chart-hotpoint').forEach(h => h.classList.remove('active'));
                hotpoint.classList.add('active');
            });
            
            wrapper.appendChild(hotpoint);
            hotpoints.push({
                element: hotpoint,
                prediction: prediction,
                coords: coords
            });
        }
        
        // 选择hotpoint并显示详情
        function selectHotpoint(prediction, index) {
            selectedHotpoint = {
                ...prediction,
                index: index
            };
            showFixedFloatingPanel(prediction, index);
        }
        
        // 显示固定悬浮面板
        function showFixedFloatingPanel(prediction, index) {
            const panel = document.getElementById('fixedFloatingPanel');
            const content = document.getElementById('panelContent');
            const title = document.getElementById('panelTitle');
            const subtitle = document.getElementById('panelSubtitle');
            
            // 更新标题
            title.textContent = `📊 预测 #${index + 1} - ${prediction.label || ''}`;
            const timeframe = prediction.timeframe || 'short_term';
            const timeframeText = timeframe === 'short_term' ? '短期' : 
                                  timeframe === 'medium_term' ? '中期' : '长期';
            subtitle.textContent = `${timeframeText} | 准确率: ${prediction.verification_accuracy || 0}%`;
            
            // 处理验证时间点数据
            const real_verification = prediction.real_verification || {};
            const check_points = real_verification.check_points || [];
            
            // 提取验证时间点索引并添加相对时间索引
            const verification_timepoints = [];
            
            // 检查点相对时间映射
            const checkPointTimeMap = {
                '24h': 1,
                '1d': 1,
                '3d': 3,
                '7d': 7,
                '14d': 14,
                '30d': 30,
                '60d': 60,
                '90d': 90,
                '180d': 180,
                '1天': 1,
                '3天': 3,
                '7天': 7,
                '14天': 14,
                '30天': 30,
                '60天': 60,
                '90天': 90,
                '1周': 7,
                '2周': 14,
                '1个月': 30,
                '2个月': 60,
                '3个月': 90
            };
            
            check_points.forEach((cp, i) => {
                // 如果已经有timeIndex，直接使用
                if (cp.timeIndex !== undefined) {
                    verification_timepoints.push(cp.timeIndex);
                } else {
                    // 否则尝试从check_point字符串推断
                    const checkPointStr = cp.check_point || '';
                    
                    // 遍历映射表查找匹配
                    for (const [key, offset] of Object.entries(checkPointTimeMap)) {
                        if (checkPointStr.includes(key)) {
                            // 添加到预测索引上
                            const timeIndex = index + offset;
                            verification_timepoints.push(timeIndex);
                            
                            // 将timeIndex添加回check_point对象
                            cp.timeIndex = timeIndex;
                            break;
                        }
                    }
                    
                    // 如果无法推断，使用索引顺序作为后备
                    if (!cp.timeIndex) {
                        const fallbackIndex = index + (i + 1) * 7; // 默认每个检查点间隔7天
                        verification_timepoints.push(fallbackIndex);
                        cp.timeIndex = fallbackIndex;
                    }
                }
            });
            
            // 绘制验证小图表
            drawMiniChart({
                ...prediction,
                index: index,
                verification_timepoints: verification_timepoints
            });
            
            // 生成详情内容
            content.innerHTML = generateDetailContent(prediction);
            
            // 更新图表说明
            const chartExplanation = content.querySelector('.detail-section:last-child div[style]');
            if (chartExplanation) {
                chartExplanation.innerHTML = `
                    上方小图显示预测点(黄色)和验证时间点(绿色)的价格走势。
                    图表范围从验证时间前5天到最晚验证结果后5天，
                    白色虚线为预测时间基准线，可直观看到后续价格验证结果。
                `;
            }
            
            // 显示面板
            panel.classList.add('show');
        }
        
        // 隐藏预测面板
        function hidePredictionPanel() {
            const panel = document.getElementById('fixedFloatingPanel');
            panel.classList.remove('show');
            
            // 取消所有hotpoint的选中状态
            document.querySelectorAll('.chart-hotpoint').forEach(h => h.classList.remove('active'));
            selectedHotpoint = null;
        }
        
        // 生成详情内容
        function generateDetailContent(prediction) {
            const accuracyClass = prediction.verification_accuracy >= 80 ? 'accuracy-excellent' :
                                 prediction.verification_accuracy >= 70 ? 'accuracy-good' :
                                 prediction.verification_accuracy >= 60 ? 'accuracy-average' : 'accuracy-poor';
            
            // 处理验证结果
            const real_verification = prediction.real_verification || {};
            const check_points = real_verification.check_points || [];
            
            const verificationItems = check_points.map(cp => {
                const checkPoint = (cp && typeof cp === 'object' ? cp.check_point : '') || 'N/A';
                const dataQuality = (cp && typeof cp === 'object' ? cp.data_quality : '') || '';

                if (dataQuality === 'pending' || (cp && typeof cp === 'object' && cp.error === '待预测')) {
                    const dateText = (cp && typeof cp === 'object' && cp.target_date) ? `<div style="opacity:0.85;margin-top:4px;font-size:0.85em;">${cp.target_date}</div>` : '';
                    return `<div class="verification-item verification-pending">
                        <strong>${checkPoint}</strong><br>
                        ⏳ 待预测
                        ${dateText}
                    </div>`;
                }

                if (cp && typeof cp === 'object' && cp.is_correct !== undefined) {
                    const isCorrect = !!cp.is_correct;
                    const change = Number(cp.price_change_percent || 0);
                    return `<div class="verification-item ${isCorrect ? 'verification-correct' : 'verification-incorrect'}">
                        <strong>${checkPoint}</strong><br>
                        ${isCorrect ? '✅' : '❌'} ${change.toFixed(1)}%
                    </div>`;
                }

                const err = (cp && typeof cp === 'object' ? (cp.error || 'Unknown error') : 'Unknown error');
                return `<div class="verification-item verification-failed">
                    <strong>${checkPoint}</strong><br>
                    ⚠️ ${err}
                </div>`;
            }).join('');
            
            return `
                <div class="prediction-details">
                    <!-- 基本信息 -->
                    <div class="detail-section">
                        <div class="section-title-small">🎯 基本信息</div>
                        <div class="detail-row">
                            <span class="detail-label">预测位置</span>
                            <span class="detail-value">${prediction.price || 'N/A'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">情绪倾向</span>
                            <span class="sentiment-badge sentiment-${prediction.sentiment}">
                                ${prediction.sentiment === 'bullish' ? '看涨' : 
                                  prediction.sentiment === 'bearish' ? '看跌' : '中性'}
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">时间范围</span>
                            <span class="detail-value">${prediction.timeframe === 'short_term' ? '短期' :
                                                         prediction.timeframe === 'medium_term' ? '中期' : '长期'}</span>
                        </div>
                    </div>
                    
                    <!-- 验证准确率 -->
                    <div class="detail-section">
                        <div class="section-title-small">📊 验证准确率</div>
                        <div class="detail-row">
                            <span class="detail-label">整体准确率</span>
                            <span class="detail-value">${prediction.verification_accuracy || 0}%</span>
                        </div>
                        <div class="accuracy-meter">
                            <div class="accuracy-fill ${accuracyClass}" style="width: ${prediction.verification_accuracy || 0}%"></div>
                        </div>
                    </div>
                    
                    <!-- 时间验证结果 -->
                    ${verificationItems ? `
                    <div class="detail-section">
                        <div class="section-title-small">⏰ 时间验证结果</div>
                        <div class="verification-grid">
                            ${verificationItems}
                        </div>
                    </div>
                    ` : ''}
                    
                    <!-- 图表说明 -->
                    <div class="detail-section">
                        <div class="section-title-small">📈 验证图表说明</div>
                        <div style="font-size: 0.85em; color: #666; line-height: 1.4;">
                            上方小图显示预测点(黄色)和验证时间点(绿色)的价格走势。
                            图表范围从验证时间前5天到最晚验证结果后5天，
                            白色虚线为预测时间基准线，可直观看到后续价格验证结果。
                        </div>
                    </div>
                </div>
            `;
        }
        
        // 初始化图表交互
        function initChartInteractions() {
            const wrapper = document.getElementById('chartWrapper');
            const img = document.getElementById('priceChartImg');
            
            if (!wrapper || !img || !predictionData || predictionData.length === 0) return;
            
            // 等待图片加载完成
            if (img.complete) {
                addAllHotpoints();
            } else {
                img.onload = function() {
                    addAllHotpoints();
                };
            }
            
            // 响应式重新定位
            let resizeTimeout;
            window.addEventListener('resize', () => {
                clearTimeout(resizeTimeout);
                resizeTimeout = setTimeout(() => {
                    setupMiniCanvas();
                    recalculateHotpoints();
                    
                    // 如果有选中的预测，重新绘制小图表
                    if (selectedHotpoint) {
                        drawMiniChart(selectedHotpoint);
                    }
                }, 100);
            });
            
            // 点击图表空白处取消选择
            wrapper.addEventListener('click', (e) => {
                if (e.target === e.currentTarget || e.target.tagName === 'IMG') {
                    hidePredictionPanel();
                }
            });
        }
        
        // 添加所有hotpoints
        function addAllHotpoints() {
            // 清除现有的hotpoints
            hotpoints.forEach(h => h.element.remove());
            hotpoints = [];
            
            // 添加新的hotpoints
            predictionData.forEach((pred, index) => {
                addCSSHotpoint(pred, index);
            });
        }
        
        // 重新计算hotpoints位置
        function recalculateHotpoints() {
            const img = document.getElementById('priceChartImg');
            if (!img) return;
            
            const imgRect = img.getBoundingClientRect();
            
            hotpoints.forEach((hotpoint, index) => {
                const newCoords = calculatePreciseCoordinates(predictionData[index], imgRect);
                hotpoint.element.style.left = `${newCoords.percentX}%`;
                hotpoint.element.style.top = `${newCoords.percentY}%`;
                hotpoint.coords = newCoords;
            });
        }
    </script>
</body>
</html>'''

    def _get_kol_list_template_complete(self) -> str:
        """获取完整的KOL列表HTML模板"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>专业级KOL分析系统 - KOL列表</title>
    <style>
        body {
            font-family: 'Segoe UI', 'Microsoft YaHei', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6; margin: 0; padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; color: #333;
        }
        .container {
            max-width: 1600px; margin: 0 auto; background: white;
            border-radius: 20px; box-shadow: 0 15px 50px rgba(0,0,0,0.25);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 50px; text-align: center;
        }
        .header h1 { font-size: 3.5em; margin-bottom: 15px; font-weight: 700; }
        .subtitle { font-size: 1.5em; opacity: 0.9; margin-bottom: 30px; }
        
        .summary-stats {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 25px; margin: 30px 0; padding: 0 20px;
        }
        .stat-card {
            background: rgba(255,255,255,0.15); padding: 25px; border-radius: 15px;
            text-align: center; backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .stat-value {
            font-size: 2.5em; font-weight: bold; color: white; margin-bottom: 10px;
        }
        .stat-label {
            font-size: 1.1em; color: rgba(255,255,255,0.8);
        }
        
        .section {
            padding: 50px;
        }
        .section-title {
            font-size: 2.2em; margin-bottom: 30px; color: #333; 
            border-bottom: 3px solid #667eea; padding-bottom: 15px;
        }
        
        .kol-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
            gap: 30px; margin-top: 30px;
        }
        
        .kol-card {
            background: white; border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
            border-left: 6px solid #667eea; position: relative;
            transition: all 0.3s ease; cursor: pointer;
            overflow: hidden;
        }
        .kol-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.2);
        }
        
        .kol-card-background {
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 120px;
            opacity: 0.9;
            z-index: 1;
        }
        
        .kol-card-content {
            position: relative;
            z-index: 2;
            padding: 30px;
            padding-top: 80px;
        }
        
        .kol-rank {
            position: absolute; top: 20px; right: 20px;
            background: rgba(255,255,255,0.9); color: #667eea; 
            padding: 5px 15px;
            border-radius: 20px; font-weight: bold;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 3;
        }
        
        .kol-header {
            display: flex; align-items: center; gap: 20px; margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .kol-avatar {
            width: 80px; height: 80px; border-radius: 50%;
            border: 4px solid white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            margin-top: -40px;
        }
        .kol-avatar.default {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex; align-items: center; justify-content: center;
            color: white; font-size: 2em; font-weight: bold;
        }
        .kol-name {
            font-size: 1.6em; font-weight: bold; color: #333;
            text-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .kol-stats {
            display: grid; grid-template-columns: repeat(3, 1fr);
            gap: 15px; margin: 20px 0;
        }
        .stat {
            text-align: center; padding: 10px;
            background: #f8f9fa; border-radius: 10px;
        }
        .stat-label {
            font-size: 0.9em; color: #666; margin-bottom: 5px;
        }
        .stat-value {
            font-size: 1.2em; font-weight: bold; color: #333;
        }
        
        .view-details-btn {
            display: inline-block; background: #667eea; color: white;
            padding: 12px 25px; border-radius: 25px; text-decoration: none;
            font-weight: bold; transition: all 0.3s ease;
            margin-top: 20px; width: 100%; text-align: center;
        }
        .view-details-btn:hover {
            background: #5a6fd8; transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        @media (max-width: 768px) {
            .container { margin: 10px; }
            .section { padding: 25px; }
            .kol-grid { grid-template-columns: 1fr; }
            .header h1 { font-size: 2.5em; }
            .summary-stats { grid-template-columns: 1fr 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏆 专业级KOL分析系统</h1>
            <div class="subtitle">基于真实历史价格验证和深度分析的综合评估</div>
            
            <div class="summary-stats">
                <div class="stat-card">
                    <div class="stat-value" id="total-kols">0</div>
                    <div class="stat-label">分析KOL总数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="avg-score">0</div>
                    <div class="stat-label">平均评分</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="avg-accuracy">0%</div>
                    <div class="stat-label">平均准确率</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="excellent-kols">0</div>
                    <div class="stat-label">优秀KOL (S/A级)</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">👥 KOL专业排行榜</h2>
            <div class="kol-grid" id="kol-grid">
                <!-- 动态生成KOL卡片 -->
            </div>
        </div>
    </div>
    
    <script>
        // KOL数据将从后端动态加载
        const kolData = {kol_data_placeholder};
        
        // 初始化页面
        document.addEventListener('DOMContentLoaded', () => {
            updateSummaryStats();
            renderKOLCards();
        });
        
        function updateSummaryStats() {
            const totalKOLs = Object.keys(kolData).length;
            let totalAccuracy = 0;
            let excellentCount = 0;
            
            Object.values(kolData).forEach(kol => {
                totalAccuracy += kol.overall_accuracy || 0;
                // 优先使用tier，如果没有则使用overall_grade
                const grade = kol.tier || kol.overall_grade || 'C';
                if (['S+', 'S', 'S-', 'A+', 'A', 'A-'].includes(grade)) {
                    excellentCount++;
                }
            });
            
            document.getElementById('total-kols').textContent = totalKOLs;
            // 不再显示数值评分，将平均评分位置设为“-”
            document.getElementById('avg-score').textContent = '-';
            document.getElementById('avg-accuracy').textContent = totalKOLs > 0 ? 
                (totalAccuracy / totalKOLs).toFixed(1) + '%' : '0%';
            document.getElementById('excellent-kols').textContent = excellentCount;
        }
        
        function renderKOLCards(filteredData = null) {
            const data = filteredData || kolData;
            const kolGrid = document.getElementById('kol-grid');
            
            // 转换为数组并排序
            const kolArray = Object.entries(data).map(([kolId, kol]) => ({
                id: kolId,
                ...kol
            }));
            
            // 默认按等级(tier)排序，若等级相同则按整体准确率排序
            const tierOrder = ['S+', 'S', 'S-', 'A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-'];
            const tierRank = (t) => (tierOrder.indexOf(t) === -1 ? tierOrder.length : tierOrder.indexOf(t));
            kolArray.sort((a, b) => {
                const ar = tierRank(a.tier || a.tier || '');
                const br = tierRank(b.tier || b.tier || '');
                if (ar !== br) return ar - br;
                return (b.overall_accuracy || 0) - (a.overall_accuracy || 0);
            });
            
            const cardsHtml = kolArray.map((kol, index) => {
                const initials = kol.initials || (kol.name ? kol.name.substring(0, 2).toUpperCase() : 'KOL');
                
                // 直接使用传递的background_style
                const backgroundStyle = kol.background_style || 'background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);';
                
                // 使用预先生成的avatar_html
                let avatarHtml;
                if (kol.avatar_html) {
                    avatarHtml = kol.avatar_html;
                } else if (kol.has_avatar && kol.avatar_image_path) {
                    avatarHtml = `<div class="kol-avatar" style="background-image: url('${kol.avatar_image_path}'); background-size: cover; background-position: center;"></div>`;
                } else {
                    avatarHtml = `<div class="kol-avatar default">${initials}</div>`;
                }
                
                // 获取分析的币种列表
                const coins = kol.analyzed_coins || [];
                
                return `
                    <div class="kol-card" onclick="viewKOLDetails('${kol.id}')">
                        <div class="kol-card-background" style="${backgroundStyle}"></div>
                        <div class="kol-rank">#${index + 1}</div>
                        <div class="kol-card-content">
                            <div class="kol-header">
                                ${avatarHtml}
                                <div style="flex: 1;">
                                    <div class="kol-name">@${kol.name}</div>
                                    <!-- 等级小卡片已移除：改为在统计栏显示等级 -->
                                </div>
                            </div>
                            
                            <div class="kol-stats">
                                <div class="stat">
                                    <div class="stat-label">整体准确率</div>
                                    <div class="stat-value">${(kol.overall_accuracy || 0).toFixed(1)}%</div>
                                </div>
                                <div class="stat">
                                    <div class="stat-label">等级</div>
                                    <div class="stat-value">${(kol.tier || kol.overall_grade || '-')}</div>
                                </div>
                                <div class="stat">
                                    <div class="stat-label">币种数</div>
                                    <div class="stat-value">${coins.length}</div>
                                </div>
                            </div>
                            
                            <div style="background: linear-gradient(135deg, #e3f2fd, #bbdefb); padding: 14px; 
                                        border-radius: 10px; margin: 15px 0; color: #0d47a1; font-size: 0.92em; 
                                        line-height: 1.5; box-shadow: 0 2px 6px rgba(0,0,0,0.08); 
                                        border-left: 4px solid #1565c0;">
                                ${kol.key_verdict || '点击查看详细分析报告'}
                            </div>
                            
                            <a href="#" class="view-details-btn" style="display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; box-sizing: border-box; background: #1976d2; color: white; text-align: center; padding: 10px; border-radius: 6px; text-decoration: none; font-weight: 500; transition: all 0.2s ease; margin-top: 5px;">查看详细分析 →</a>
                        </div>
                    </div>
                `;
            }).join('');
            
            kolGrid.innerHTML = cardsHtml;
        }
        
        function viewKOLDetails(kolId) {
            window.location.href = `./kol_reports/${kolId}_analysis.html`;
        }
    </script>
</body>
</html>'''

    def _get_kol_coins_template_complete(self) -> str:
        """获取完整的KOL币种HTML模板"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@{kol_name} - 专业分析报告</title>
    <style>
        body {
            font-family: 'Segoe UI', 'Microsoft YaHei', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6; margin: 0; padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; color: #333;
        }
        .container {
            max-width: 1800px; margin: 0 auto; background: white;
            border-radius: 20px; box-shadow: 0 15px 50px rgba(0,0,0,0.25);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 50px; text-align: center;
            position: relative;
            overflow: hidden;
        }
        
        .header-background {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            opacity: 0.3;
            filter: blur(3px);
            z-index: 0;
        }
        
        .header-content {
            position: relative;
            z-index: 1;
        }
        
        .back-btn {
            position: absolute; top: 20px; left: 20px;
            background: rgba(255,255,255,0.2); color: white;
            padding: 10px 20px; border-radius: 25px; text-decoration: none;
            font-weight: bold; backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            z-index: 2;
        }
        .back-btn:hover {
            background: rgba(255,255,255,0.3);
            transform: translateX(-5px);
        }
        .header h1 { 
            font-size: 3em; margin-bottom: 15px; font-weight: 700; 
            display: flex; align-items: center; justify-content: center; gap: 20px;
        }
        .kol-avatar {
            width: 100px; height: 100px; border-radius: 50%;
            border: 5px solid white;
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
        }
        .kol-avatar.default {
            background: white; color: #667eea;
            display: flex; align-items: center; justify-content: center;
            font-size: 2.5em; font-weight: bold;
        }
        .subtitle { font-size: 1.3em; opacity: 0.9; margin-bottom: 30px; }
        
        .section {
            padding: 50px;
        }
        .section-title {
            font-size: 2.2em; margin-bottom: 30px; color: #333; 
            border-bottom: 3px solid #667eea; padding-bottom: 15px;
        }
        
        .coin-analysis-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 30px; margin-top: 30px;
        }
        .coin-card {
            background: white; border-radius: 20px; padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
            border-top: 5px solid #667eea;
            transition: all 0.3s ease; cursor: pointer;
            position: relative;
        }
        .coin-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.2);
        }
        
        .coin-header {
            display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 20px;
        }
        .coin-name {
            font-size: 1.6em; font-weight: bold; color: #333;
            display: flex; align-items: center; gap: 10px;
        }
        .coin-icon {
            width: 40px; height: 40px; border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex; align-items: center; justify-content: center;
            color: white; font-weight: bold;
        }
        
        .coin-stats {
            display: grid; grid-template-columns: 1fr 1fr;
            gap: 15px; margin: 20px 0;
        }
        .coin-stat {
            text-align: center; padding: 10px;
            background: #f8f9fa; border-radius: 10px;
        }
        .coin-stat-label {
            font-size: 0.9em; color: #666; margin-bottom: 5px;
        }
        .coin-stat-value {
            font-size: 1.3em; font-weight: bold; color: #333;
        }
        
        .view-analysis-btn {
            display: block; background: #667eea; color: white;
            padding: 12px 25px; border-radius: 25px; text-decoration: none;
            font-weight: bold; transition: all 0.3s ease;
            margin-top: 20px; text-align: center;
        }
        .view-analysis-btn:hover {
            background: #5a6fd8; transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        /* 专业表现指标 - 增强版样式 */
        .professional-metrics-enhanced {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin: 30px 0;
        }

        .metric-card-large {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 20px;
            padding: 35px;
            color: white;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 25px;
        }

        .metric-card-large:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(102, 126, 234, 0.4);
        }

        .metric-card-large.metric-excellent {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }

        .metric-card-large.metric-good {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }

        .metric-card-large.metric-average {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        }

        .metric-card-large.metric-poor {
            background: linear-gradient(135deg, #ee9ca7 0%, #ffdde1 100%);
        }

        .metric-card-large.metric-tier {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }

        .metric-icon {
            font-size: 4em;
            opacity: 0.9;
            flex-shrink: 0;
        }

        .metric-content {
            flex: 1;
        }

        .metric-value-large {
            font-size: 3.5em;
            font-weight: 900;
            line-height: 1;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }

        .metric-label-large {
            font-size: 1.2em;
            opacity: 0.95;
            font-weight: 600;
            margin-bottom: 15px;
        }

        .metric-subtitle {
            font-size: 0.9em;
            opacity: 0.8;
            margin-top: 10px;
        }

        .metric-progress {
            height: 8px;
            background: rgba(255,255,255,0.3);
            border-radius: 10px;
            overflow: hidden;
            margin-top: 15px;
        }

        .metric-progress-bar {
            height: 100%;
            background: white;
            border-radius: 10px;
            transition: width 1s ease;
            box-shadow: 0 0 10px rgba(255,255,255,0.5);
        }

        @media (max-width: 768px) {
            .container { margin: 10px; }
            .section { padding: 25px; }
            .coin-analysis-grid { grid-template-columns: 1fr; }
            .header h1 { font-size: 2em; flex-direction: column; }
            .professional-metrics-enhanced {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-background" style="{background_style}"></div>
            <a href="../index.html" class="back-btn">← 返回KOL列表</a>
            <div class="header-content">
                <h1>
                    {avatar_html}
                    @{kol_name}
                </h1>
                <div class="subtitle">专业级加密货币分析师评估报告</div>
                
                <div style="background: rgba(255,255,255,0.1); margin: 30px 0; 
                            padding: 25px; border-radius: 15px;">
                    <h3 style="margin-top: 0;">📋 执行摘要</h3>
                    <p style="margin-bottom: 0; font-size: 1.1em; line-height: 1.7;">
                        {key_verdict}
                    </p>
                </div>
            </div>
        </div>
        
        <!-- Professional Metrics -->
        <div class="section">
            <h2 class="section-title">📊 专业表现指标</h2>
            {professional_metrics}
        </div>
        
        <!-- Coin Analysis -->
        <div class="section">
            <h2 class="section-title">🪙 币种分析逻辑链</h2>
            
            <div class="coin-analysis-grid" id="coin-grid">
                <!-- 动态生成币种分析卡片 -->
            </div>
        </div>
    </div>
    
    <script>
        // 币种数据将从后端动态加载
        const coinAnalysisData = {coin_analysis_data_placeholder};
        
        document.addEventListener('DOMContentLoaded', () => {
            renderCoinCards();
        });
        
        function renderCoinCards() {
            const coinGrid = document.getElementById('coin-grid');

            // 生成卡片HTML
            const cardsHtml = coinAnalysisData.map(coin => {
                const accuracyClass = coin.overall_accuracy >= 80 ? 'accuracy-high' :
                                     coin.overall_accuracy >= 60 ? 'accuracy-medium' : 'accuracy-low';

                return `
                    <div class="coin-card" onclick="viewCoinAnalysis('${coin.coin_id}')">
                        <div class="coin-header">
                            <div class="coin-name">
                                <div class="coin-icon">${coin.coin_name.substring(0, 2).toUpperCase()}</div>
                                ${coin.coin_name}
                            </div>
                        </div>

                        <div class="coin-stats">
                            <div class="coin-stat">
                                <div class="coin-stat-label">准确率</div>
                                <div class="coin-stat-value ${accuracyClass}">
                                    ${coin.overall_accuracy.toFixed(1)}%
                                </div>
                            </div>
                            <div class="coin-stat">
                                <div class="coin-stat-label">预测数量</div>
                                <div class="coin-stat-value">${coin.total_predictions}</div>
                            </div>
                        </div>

                        <div style="background: #e3f2fd; padding: 15px; border-radius: 10px; margin: 15px 0;
                                    color: #1565c0; line-height: 1.6;">
                            ${coin.summary}
                        </div>

                        <a href="#" class="view-analysis-btn">查看详细推理链 →</a>
                    </div>
                `;
            }).join('');

            coinGrid.innerHTML = cardsHtml || '<div style="text-align: center; color: #666; padding: 50px;">暂无币种分析数据</div>';
        }
        
        function viewCoinAnalysis(coinId) {
            // 跳转到具体币种的详细分析页面
            const kolName = '{kol_name}';
            window.location.href = `../coin_reports/${kolName}_${coinId}_analysis.html`;
        }
    </script>
</body>
</html>'''


# 导出
__all__ = ['HTMLReportGenerator']
