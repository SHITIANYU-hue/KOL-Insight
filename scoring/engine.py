from typing import List, Optional
import json
import os
import asyncio
import inspect
from dataclasses import fields
from models.data_model import Account
from models.score_node import ScoreNode
from utils import call_gpt
from scoring.normalization_manager import NormalizationManager


# 使用 DFS 迭代寻找 leaf_nodes
def find_leaf_nodes(node: ScoreNode):
    leaf_nodes = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current.is_leaf():
            leaf_nodes.append(current)
        else:
            stack.extend(current.children)
    return leaf_nodes

# 后序遍历
def post_order_traversal(node: ScoreNode) -> List[tuple[ScoreNode, int]]:
    """获取所有节点及其深度"""
    nodes_with_depth = []
    stack = [(node, 0)]
    while stack:
        current, depth = stack.pop()
        nodes_with_depth.append((current, depth))
        for child in current.children:
            stack.append((child, depth + 1))
    nodes_with_depth.sort(key=lambda x: x[1], reverse=True) # 深度从大到小排序
    return nodes_with_depth


async def generate_root_comment(account: Account, account_idx: int, root_score: float, root: ScoreNode, scores: dict, comments: dict, normalization_params: dict) -> str:
    """为根节点生成AI评论"""
    try:
        # 动态获取所有叶节点
        leaf_nodes = find_leaf_nodes(root)
        
        # 动态获取Account字段（排除tweets等不需要的字段）
        account_fields_to_exclude = {'tweets', 'user_id'}  # 排除的字段
        account_info_list = []
        for field in fields(Account):
            if field.name not in account_fields_to_exclude:
                value = getattr(account, field.name, None)
                if value is None:
                    value = '无' if field.type == str or (hasattr(field.type, '__origin__') and field.type.__origin__ is str) else 0
                account_info_list.append(f"- {field.name}: {value}")
        account_info = "\n".join(account_info_list)
        
        # 动态获取各个维度的得分和评语
        dimension_info_list = []
        for leaf_node in leaf_nodes:
            key = leaf_node.key
            name = leaf_node.name
            if key in scores and key in comments:
                score = scores[key][account_idx] if account_idx < len(scores[key]) else 0.0
                comment = comments[key][account_idx] if account_idx < len(comments[key]) else ""
                # 判断是否归一化：直接使用leaf_node.normalize属性
                is_normalized = leaf_node.normalize
                score_label = f"{score:.2%}" if is_normalized else f"{score:.2f}"
                dimension_info_list.append(f"- {name} ({key}): 得分 {score_label}" + (" [已归一化]" if is_normalized else " [原始分]") + f", 评语: {comment}")
        
        dimension_info = "\n".join(dimension_info_list)
        
        # 构建提示词
        prompt = f"""请基于以下KOL的综合评分信息，生成一段整体评论。

账号信息：
{account_info}

各维度评分：
{dimension_info}

综合评分（根节点得分，已归一化）: {root_score:.2%}

请生成一段综合评论，总结该KOL的整体表现，包括优势、不足和建议。评论应该：
1. 简洁明了（100-200字）
2. 基于各个维度的得分和评语
3. 提供有价值的洞察
4. 用中文表达

请直接返回评论内容，不要添加其他格式。"""
        
        result = await call_gpt(prompt, None)  # 不使用json_schema，直接返回文本
        if isinstance(result, dict):
            return result.get("comment", "无法生成评论")
        return str(result) if result else "无法生成评论"
    except Exception as e:
        print(f"生成根节点评论时发生错误（账号 {getattr(account, 'username', '未知')}）: {e}")
        return "无法生成评论"


async def calculate(accounts: List[Account], root: ScoreNode, 
                   normalization_manager: Optional[NormalizationManager] = None,
                   save_history: bool = True):
    """
    计算评分
    
    Args:
        accounts: 账号列表
        root: 评分树根节点
        normalization_manager: 归一化参数管理器（如果提供，将使用已有的归一化参数）
        save_history: 是否保存原始分数到历史记录
    """
    # 初始化归一化管理器
    if normalization_manager is None:
        normalization_manager = NormalizationManager()
        normalization_manager.load_normalization_params()
    
    # 1. 找到所有叶节点
    leaf_nodes = find_leaf_nodes(root)
    
    # 2. 并发计算所有叶节点的原始分和评语
    async def calc_account_score(leaf_node: ScoreNode, account: Account):
        """计算单个账号在某个叶节点的得分和评语，返回 (score, comment)"""
        if leaf_node.calc_raw is None:
            return (0.0, "")
        
        # 兼容同步和异步函数
        if inspect.iscoroutinefunction(leaf_node.calc_raw):
            try:
                result = await leaf_node.calc_raw(account)
            except Exception as e:
                print(f"计算叶节点 {leaf_node.key} 得分时发生错误: {e}")
                return (0.0, "")
        else:
            try:
                result = leaf_node.calc_raw(account)
            except Exception as e:
                print(f"计算叶节点 {leaf_node.key} 得分时发生错误: {e}")
                return (0.0, "")
        
        # 处理返回格式：可能是 float 或 (float, str) 元组
        if isinstance(result, tuple) and len(result) == 2:
            return result
        else:
            return (float(result), "")
    
    # 并发计算所有账号在所有叶节点的得分和评语
    scores = {leaf_node.key: [] for leaf_node in leaf_nodes}
    comments = {leaf_node.key: [] for leaf_node in leaf_nodes}
    raw_scores = {}  # 保存原始分（归一化之前）
    normalization_params = {}  # 保存归一化参数（min和max）
    
    for leaf_node in leaf_nodes:
        # 为每个账号创建计算任务
        tasks = [calc_account_score(leaf_node, account) for account in accounts]
        # 并发执行所有任务
        results = await asyncio.gather(*tasks)
        leaf_scores = [r[0] for r in results]
        leaf_comments = [r[1] for r in results]
        scores[leaf_node.key] = leaf_scores
        comments[leaf_node.key] = leaf_comments
        raw_scores[leaf_node.key] = leaf_scores.copy()  # 保存原始分
    
    # 保存原始分数到历史记录
    if save_history:
        # 提取用户名列表
        usernames = [getattr(account, 'username', f'user_{idx}') for idx, account in enumerate(accounts)]
        normalization_manager.save_history(raw_scores, usernames)
    
    # 3. 叶节点归一化（只对normalize为True的叶节点生效）
    for leaf_node in leaf_nodes:
        if leaf_node.normalize:
            leaf_key = leaf_node.key
            
            # 检查是否有已有的归一化参数
            if leaf_key in normalization_manager.normalization_params:
                # 使用已有的归一化参数
                params = normalization_manager.normalization_params[leaf_key]
                min_score = params.get("min", 0.0)
                max_score = params.get("max", 1.0)
                normalization_params[leaf_key] = {"min": min_score, "max": max_score}
                
                # 使用已有参数进行归一化
                if max_score == min_score:
                    scores[leaf_key] = [0.0] * len(scores[leaf_key])
                else:
                    scores[leaf_key] = [
                        normalization_manager.normalize_score(leaf_key, raw_score)
                        for raw_score in raw_scores[leaf_key]
                    ]
                print(f"   使用已有归一化参数: {leaf_key} (min={min_score:.4f}, max={max_score:.4f})")
            else:
                # 使用当前批次数据计算归一化参数
                min_score = min(raw_scores[leaf_key])
                max_score = max(raw_scores[leaf_key])
                normalization_params[leaf_key] = {"min": min_score, "max": max_score}
                
                if max_score == min_score:
                    scores[leaf_key] = [0.0] * len(scores[leaf_key])
                else:
                    scores[leaf_key] = [(s - min_score) / (max_score - min_score) for s in raw_scores[leaf_key]]
                print(f"   使用当前批次计算归一化参数: {leaf_key} (min={min_score:.4f}, max={max_score:.4f})")
    
    # 4. 递归计算所有节点的得分（从下往上）
    nodes_with_depth = post_order_traversal(root)

    # 初始化所有节点的得分和评语
    for node, _ in nodes_with_depth:
        if node.key not in scores:
            scores[node.key] = [0.0] * len(accounts)
        if node.key not in comments:
            comments[node.key] = [""] * len(accounts)
        # 非叶节点的原始分初始化为0（会在计算时填充）
        if node.key not in raw_scores:
            raw_scores[node.key] = [0.0] * len(accounts)
    
    # 从下往上计算非叶节点的得分
    for node, _ in nodes_with_depth:
        if not node.is_leaf():
            # 特殊处理：根节点使用乘法计算 (other_factors的平均 × human_vitality)
            if node.key == "root" and len(node.children) == 2:
                # 找到other_factors和human_vitality节点
                other_factors_child = None
                human_vitality_child = None
                for child in node.children:
                    if child.key == "other_factors":
                        other_factors_child = child
                    elif child.key == "human_vitality":
                        human_vitality_child = child
                
                if other_factors_child and human_vitality_child:
                    # 根节点得分 = other_factors得分 × human_vitality得分
                    for account_idx in range(len(accounts)):
                        other_factors_score = scores[other_factors_child.key][account_idx]
                        human_vitality_score = scores[human_vitality_child.key][account_idx]
                        final_score = other_factors_score * human_vitality_score
                        scores[node.key][account_idx] = final_score
                        raw_scores[node.key][account_idx] = final_score
                else:
                    # 如果找不到两个子节点，使用加权平均
                    total_weight = sum(child.weight for child in node.children)
                    if total_weight > 0:
                        normalized_weights = {child.key: child.weight / total_weight for child in node.children}
                    else:
                        normalized_weights = {child.key: 0.0 for child in node.children}
                    
                    for account_idx in range(len(accounts)):
                        weighted_sum = 0.0
                        for child in node.children:
                            child_score = scores[child.key][account_idx]
                            child_normalized_weight = normalized_weights[child.key]
                            weighted_sum += child_score * child_normalized_weight
                        scores[node.key][account_idx] = weighted_sum
                        raw_scores[node.key][account_idx] = weighted_sum
            else:
                # 其他非叶节点使用加权平均（归一化weight）
                total_weight = sum(child.weight for child in node.children)
                if total_weight > 0:
                    normalized_weights = {child.key: child.weight / total_weight for child in node.children}
                else:
                    normalized_weights = {child.key: 0.0 for child in node.children}
                
                # 计算每个账户的得分
                for account_idx in range(len(accounts)):
                    weighted_sum = 0.0
                    for child in node.children:
                        child_score = scores[child.key][account_idx]
                        child_normalized_weight = normalized_weights[child.key]
                        weighted_sum += child_score * child_normalized_weight
                    scores[node.key][account_idx] = weighted_sum
                    raw_scores[node.key][account_idx] = weighted_sum  # 非叶节点的原始分等于归一化后的分数（因为不进行归一化）
    
    # 5. 为根节点生成AI评论
    if "root" in scores:
        # 并发为每个账号生成评论
        tasks = [
            generate_root_comment(account, idx, scores["root"][idx], root, scores, comments, normalization_params)
            for idx, account in enumerate(accounts)
        ]
        root_comments = await asyncio.gather(*tasks)
        comments["root"] = list(root_comments)
    
    return {
        "raw_scores": raw_scores,
        "normalization_params": normalization_params,
        "scores": scores,
        "comments": comments
    }


def save_tree_structure(root: ScoreNode, output_path: str = "outputs/tree_structure.json"):
    """将ScoreNode树结构保存为JSON文件"""
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 将树结构转换为字典
    tree_dict = root.to_dict()
    
    # 保存为JSON文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tree_dict, f, ensure_ascii=False, indent=2)
    