#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新归一化参数脚本

基于历史原始分数重新计算归一化参数（min/max）

使用方法:
    python update_normalization.py
"""

import os
import sys
from pathlib import Path
from scoring.normalization_manager import NormalizationManager


def main():
    """主函数"""
    print("=" * 60)
    print("归一化参数更新工具")
    print("=" * 60)
    print()
    
    # 初始化管理器
    manager = NormalizationManager()
    
    # 加载历史数据
    print("[步骤 1/2] 加载历史原始分数...")
    print("-" * 60)
    history = manager.load_history()
    
    if not history:
        print("❌ 没有找到历史原始分数数据")
        print(f"   历史文件路径: {manager.history_file}")
        print()
        print("💡 提示:")
        print("   1. 确保已经运行过 generate_report.py 至少一次")
        print("   2. 历史数据会自动保存在 outputs/raw_scores_history.json")
        return 1
    
    # 统计信息
    total_points = sum(len(scores) for scores in history.values())
    print(f"   共找到 {len(history)} 个叶节点的历史数据")
    print(f"   总计 {total_points} 个数据点")
    print()
    
    # 更新归一化参数
    print("[步骤 2/2] 更新归一化参数...")
    print("-" * 60)
    manager.update_normalization_params(use_history=True)
    
    print()
    print("=" * 60)
    print("✅ 完成！")
    print("=" * 60)
    print(f"📄 归一化参数已保存到: {manager.norm_params_file}")
    print()
    print("💡 下次运行 generate_report.py 时会自动使用更新后的归一化参数")
    
    return 0


if __name__ == "__main__":
    exit(main())

