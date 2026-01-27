#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
归一化参数管理器
- 加载已有的归一化参数
- 保存每次计算的原始分数
- 更新归一化参数
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, List


class NormalizationManager:
    """归一化参数管理器"""
    
    def __init__(self, base_dir: str = "outputs"):
        """
        初始化管理器
        
        Args:
            base_dir: 输出目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        # 归一化参数文件路径
        self.norm_params_file = self.base_dir / "normalization_params.json"
        
        # 历史原始分数文件路径
        self.history_file = self.base_dir / "raw_scores_history.json"
        
        # 归一化参数
        self.normalization_params: Dict[str, Dict[str, float]] = {}
        
        # 历史原始分数（新格式：按用户名组织）
        # 格式: {username: {leaf_key: score}}
        self.raw_scores_history: Dict[str, Dict[str, float]] = {}
    
    def load_normalization_params(self, file_path: Optional[str] = None) -> Dict[str, Dict[str, float]]:
        """
        加载归一化参数
        
        Args:
            file_path: 归一化参数文件路径（如果为 None，使用默认路径 outputs/normalization_params.json）
            
        Returns:
            归一化参数字典，格式: {leaf_key: {"min": float, "max": float}}
        """
        if file_path:
            norm_file = Path(file_path)
        else:
            norm_file = self.norm_params_file
        
        if norm_file.exists():
            try:
                with open(norm_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 如果文件直接包含 normalization_params，提取它
                    if 'normalization_params' in data:
                        self.normalization_params = data['normalization_params']
                    else:
                        self.normalization_params = data
                    print(f"✅ 已加载归一化参数: {norm_file}")
                    print(f"   包含 {len(self.normalization_params)} 个叶节点的参数")
                    return self.normalization_params
            except Exception as e:
                print(f"❌ 加载归一化参数失败: {e}")
                return {}
        else:
            print(f"⚠️  归一化参数文件不存在: {norm_file}")
            print(f"   将使用当前批次数据计算归一化参数")
            return {}
    
    def save_normalization_params(self, file_path: Optional[str] = None):
        """
        保存归一化参数
        
        Args:
            file_path: 保存路径（如果为 None，使用默认路径）
        """
        if file_path:
            norm_file = Path(file_path)
        else:
            norm_file = self.norm_params_file
        
        norm_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(norm_file, 'w', encoding='utf-8') as f:
            json.dump(self.normalization_params, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已保存归一化参数到: {norm_file}")
    
    def load_history(self) -> Dict[str, Dict[str, float]]:
        """
        加载历史原始分数
        
        Returns:
            历史原始分数字典，格式: {username: {leaf_key: score}}
            兼容旧格式: {leaf_key: [score1, score2, ...]}
        """
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 检查是否为旧格式（按 leaf_key 组织）
                    # 旧格式：{leaf_key: [score1, score2, ...]}
                    # 新格式：{username: {leaf_key: score}}
                    if data and len(data) > 0:
                        first_value = list(data.values())[0]
                        if isinstance(first_value, list):
                            # 旧格式：{leaf_key: [score1, score2, ...]}
                            print("⚠️  检测到旧格式的历史数据，将转换为新格式")
                            self.raw_scores_history = {}
                            # 由于旧格式没有用户名信息，无法完全转换，保留为空
                            print("   注意：旧格式数据无法按用户名组织，将重新开始记录")
                        else:
                            # 新格式：{username: {leaf_key: score}}
                            self.raw_scores_history = data
                    else:
                        # 空数据
                        self.raw_scores_history = {}
                    
                total_users = len(self.raw_scores_history)
                print(f"✅ 已加载历史原始分数: {total_users} 个用户")
                return self.raw_scores_history
            except Exception as e:
                print(f"❌ 加载历史原始分数失败: {e}")
                return {}
        else:
            return {}
    
    def save_history(self, raw_scores: Dict[str, List[float]], usernames: List[str]):
        """
        保存原始分数到历史记录（按用户名去重，只保留最新记录）
        
        Args:
            raw_scores: 本次计算的原始分数，格式: {leaf_key: [score1, score2, ...]}
            usernames: 用户名列表，与 raw_scores 中的分数列表一一对应
        """
        # 加载已有历史
        self.load_history()
        
        # 按用户名更新记录（如果用户名已存在，则覆盖；不存在则添加）
        updated_count = 0
        new_count = 0
        
        for idx, username in enumerate(usernames):
            if username not in self.raw_scores_history:
                self.raw_scores_history[username] = {}
                new_count += 1
            else:
                updated_count += 1
            
            # 更新该用户的所有叶节点分数
            for leaf_key, scores in raw_scores.items():
                if idx < len(scores):
                    self.raw_scores_history[username][leaf_key] = scores[idx]
        
        # 保存
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.raw_scores_history, f, ensure_ascii=False, indent=2)
        
        total_users = len(self.raw_scores_history)
        if updated_count > 0:
            print(f"✅ 已保存原始分数到历史记录: {total_users} 个用户（更新 {updated_count} 个，新增 {new_count} 个）")
        else:
            print(f"✅ 已保存原始分数到历史记录: {total_users} 个用户（新增 {new_count} 个）")
    
    def update_normalization_params(self, use_history: bool = True):
        """
        基于历史数据更新归一化参数
        
        Args:
            use_history: 是否使用历史数据（True）或仅使用当前归一化参数（False）
        """
        if use_history:
            self.load_history()
        
        if not self.raw_scores_history:
            print("⚠️  没有历史数据，无法更新归一化参数")
            return
        
        # 从新格式中提取所有分数：{username: {leaf_key: score}} -> {leaf_key: [score1, score2, ...]}
        scores_by_leaf = {}
        for username, user_scores in self.raw_scores_history.items():
            for leaf_key, score in user_scores.items():
                if leaf_key not in scores_by_leaf:
                    scores_by_leaf[leaf_key] = []
                scores_by_leaf[leaf_key].append(score)
        
        # 为每个叶节点计算新的 min/max
        updated_params = {}
        for leaf_key, scores in scores_by_leaf.items():
            if scores:
                min_score = min(scores)
                max_score = max(scores)
                updated_params[leaf_key] = {
                    "min": min_score,
                    "max": max_score
                }
                print(f"   {leaf_key}: min={min_score:.4f}, max={max_score:.4f} (基于 {len(scores)} 个数据点)")
        
        self.normalization_params = updated_params
        self.save_normalization_params()
        print(f"✅ 已更新归一化参数: {len(updated_params)} 个叶节点")
    
    def normalize_score(self, leaf_key: str, raw_score: float) -> float:
        """
        使用已有归一化参数对原始分数进行归一化
        
        Args:
            leaf_key: 叶节点键
            raw_score: 原始分数
            
        Returns:
            归一化后的分数（0-1）
        """
        if leaf_key not in self.normalization_params:
            # 如果没有归一化参数，返回原始分数（假设已经在 0-1 范围内）
            return raw_score
        
        params = self.normalization_params[leaf_key]
        min_score = params.get("min", 0.0)
        max_score = params.get("max", 1.0)
        
        if max_score == min_score:
            return 0.0
        
        normalized = (raw_score - min_score) / (max_score - min_score)
        # 限制在 0-1 范围内
        return max(0.0, min(1.0, normalized))
    
    def get_normalization_params(self) -> Dict[str, Dict[str, float]]:
        """获取当前归一化参数"""
        return self.normalization_params.copy()

