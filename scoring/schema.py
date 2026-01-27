import math
from models.data_model import Account
from models.score_node import ScoreNode
from utils import call_gpt

# 辅助函数：根据分数段生成默认评语
def get_default_comment(score: float, thresholds: list, comments: list) -> str:
    """根据分数段返回默认评语"""
    for i, threshold in enumerate(thresholds):
        if score >= threshold:
            return comments[i]
    return comments[-1]

# 1. Originality - 原创性
def originality_score(account: Account):
    if not account.tweets:
        return (0.0, "无推文数据")
    
    total_tweets = len(account.tweets)
    original_count = 0
    
    for tweet in account.tweets:
        # 判断是否是转发：in_reply_to_status_id_str 为 '1' 或 is_quote_status 为 1
        is_repost = (
            (tweet.in_reply_to_status_id_str and tweet.in_reply_to_status_id_str == '1') or
            (tweet.is_quote_status and tweet.is_quote_status == 1)
        )
        
        if not is_repost:
            original_count += 1
    
    # 计算原创比例
    originality_ratio = original_count / total_tweets if total_tweets > 0 else 0.0
    
    # 转换为0-100分数
    score = originality_ratio
    
    # 根据分数段生成评语
    thresholds = [0.8, 0.6, 0.4, 0.2]
    comments = [
        "Excellent: Content is primarily original, almost never reposts",
        "Good: Mostly original content with occasional sharing",
        "Average: Balance of original and shared content",
        "Fair: Mostly shares with limited original content",
        "Poor: Almost no original content, mainly reposts"
    ]
    comment = get_default_comment(score, thresholds, comments)
    comment = f"{comment} (原创推文: {original_count}/{total_tweets}, 比例: {originality_ratio:.2f})"
    
    return (score, comment)

originality_node = ScoreNode(
    key="originality",
    name="Originality",
    description="Ratio of original content to reposts. Measured by calculating the ratio of original tweets to total tweets. Higher ratio indicates more original content.",
    weight=1.0,
    normalize=False,
    calc_raw=originality_score
)

# 2. Bot Impact - 机器人影响
async def bot_impact_score(account: Account):
    if not account.tweets:
        return (0.0, "无推文数据")
    
    # 计算views/follower比例
    total_views = sum(t.views_count for t in account.tweets if t.views_count)
    avg_views_per_tweet = total_views / len(account.tweets) if account.tweets else 0
    views_follower_ratio = avg_views_per_tweet / account.followers_count if account.followers_count > 0 else 0
    
    # 计算互动率异常
    total_interactions = sum(t.likes_count + t.retweets_count + t.replies_count for t in account.tweets)
    engagement_rate = total_interactions / total_views if total_views > 0 else 0
    
    # 使用LLM评估机器人活动
    tweets_text = account.get_tweets_text()
    json_schema = {
        "bot_score": "机器人活动分数，0-100的整数，越高表示机器人活动越多",
        "anomaly_detection": "异常检测结果，描述发现的异常模式",
        "comment": "评语，简要说明机器人活动情况"
    }
    prompt = f"""请评估这个账号的互动真实性。分析以下指标：
- 平均每条推文的浏览量/粉丝数比例: {views_follower_ratio:.4f}
- 平均互动率（点赞+转推+回复）/浏览量: {engagement_rate:.4f}
- 粉丝数: {account.followers_count}
- 推文数: {len(account.tweets)}

推文内容：
{tweets_text}

请评估是否存在机器人活动、假粉丝、刷量等异常情况。给出机器人活动分数（0-100），分数越高表示机器人活动越多，真实性越低。然后转换为真实性分数（100-机器人活动分数）。评分不要太严格，如果没有明显机器人活动，可以按照70分左右回复。请按照JSON结构回复。"""
    
    result = await call_gpt(prompt, json_schema)
    bot_score = float(result.get("bot_score", 70))
    authenticity_score = (100 - bot_score) / 100
    comment = result.get("comment", "")
    print(f"有多像人: {authenticity_score}")
    return (authenticity_score, comment)

human_vitality_node = ScoreNode(
    key="human_vitality",
    name="Human Vitality",
    description="Human authenticity assessment. Evaluates views/follower ratio anomalies and manually tagged manipulation. Bidirectional anomaly detection identifies both engagement inflation and fake followers.",
    weight=1.0,
    normalize=False,
    calc_raw=bot_impact_score
)

# 3. KOL Influence - KOL影响力
def kol_influence_score(account: Account):
    # 基于friends_count，归一化会在engine中完成
    friends_count = account.friends_count or 0
    
    if friends_count == 0:
        return (0.0, "无KOL连接数据")
    
    # 返回原始值，归一化在engine中完成
    comment = f"KOL连接数: {friends_count}"
    return (float(friends_count), comment)

kol_influence_node = ScoreNode(
    key="kol_influence",
    name="KOL Influence",
    description="Recognition and connectivity within KOL community. Based on author's connections to other KOLs (author_friends_count). Normalized to compare KOLs of different scales.",
    weight=1.0,
    calc_raw=kol_influence_score
)

# 4. Content Depth - 内容深度
async def content_depth_score(account: Account):
    if not account.tweets:
        return (0.0, "无推文内容")
    
    # 使用LLM评估每条推文的内容深度
    tweets_text = "\n\n".join([f"推文{i+1}: {t.full_text}" for i, t in enumerate(account.tweets)])
    json_schema = {
        "tweets": [{"index": "推文序号（从1开始）", "depth_score": "内容深度分数，0-100的整数，越高表示内容越深入"}],
        "comment": "评语，简要说明内容深度情况"
    }
    result = await call_gpt(f"请评估每条推文的内容深度。内容深度包括：分析的深入程度、洞察的质量、提供的信息价值等。对每条推文给出深度分数（0-100），分数越高表示内容越深入、越有洞察力。请按照JSON结构回复。\n\n推文内容：\n\n{tweets_text}", json_schema)
    
    depth_scores = []
    for item in result.get("tweets", []):
        depth_scores.append(float(item.get("depth_score", 0)))
    
    if not depth_scores:
        return (0.0, "无法评估内容深度")
    
    avg_depth = sum(depth_scores) / len(depth_scores)
    comment = result.get("comment", f"平均内容深度: {avg_depth:.2f}")
    print(f"内容深度得分: {avg_depth}")
    return (avg_depth, comment)

content_depth_node = ScoreNode(
    key="content_depth",
    name="Content Depth",
    description="Content analysis depth and quality. Calculated as the average depth score (depth_score) across all tweets, reflecting overall content quality.",
    weight=1.0,
    calc_raw=content_depth_score
)

# 5. Engagement - 参与度
def engagement_score(account: Account):
    if not account.tweets:
        return (0.0, "无推文数据")
    
    total_interactions = sum(t.likes_count + t.retweets_count + t.replies_count for t in account.tweets)
    total_views = sum(t.views_count for t in account.tweets if t.views_count)
    
    if total_views == 0:
        return (0.0, "无浏览量数据")
    
    engagement_rate = total_interactions / total_views
    
    # 转换为0-100分数（假设正常互动率在0.01-0.1之间，超过0.1算很高）
    # 这里直接返回原始比例，归一化会在engine中完成
    score = engagement_rate * 1000  # 放大以便区分
    
    thresholds = [0.08, 0.06, 0.04, 0.02]
    comments = [
        "参与度极高，受众互动积极",
        "参与度良好，受众有一定互动",
        "参与度中等",
        "参与度较低",
        "参与度很低"
    ]
    comment = get_default_comment(engagement_rate, thresholds, comments)
    
    return (score, comment)

engagement_node = ScoreNode(
    key="engagement",
    name="Engagement",
    description="Audience interaction with content. Calculated via total_interactions/views_count, measuring content's ability to drive user action.",
    weight=1.0,
    calc_raw=engagement_score
)

# 6. Views - 浏览量
def views_score(account: Account):
    if not account.tweets:
        return (0.0, "无推文数据")
    
    total_views = sum(t.views_count for t in account.tweets if t.views_count)
    avg_views = total_views / len(account.tweets) if account.tweets else 0
    
    if avg_views <= 0:
        return (0.0, "无浏览量数据")
    
    # 对数变换
    log_views = math.log(avg_views + 1)
    
    # 返回对数变换后的值，归一化会在engine中完成
    # thresholds基于对数变换后的值，分布情况：典型KOL范围约在5.5-9.5之间
    # log(1000+1)≈6.9, log(10000+1)≈9.2, log(100000+1)≈11.5
    thresholds = [8.5, 7.5, 6.5, 5.5]
    comments = [
        "浏览量极高，覆盖范围广泛。平均每条推文浏览量通常在数万级别，处于KOL群体的前10-15%水平，显示出强大的内容传播力和影响力，能够触达大量目标受众，适合进行品牌推广和大规模营销活动。",
        "浏览量较高，覆盖范围良好。平均每条推文浏览量通常在数千到上万级别，处于KOL群体的前30-40%水平，内容传播效果良好，能够有效触达目标受众群体，具备一定的品牌推广价值。",
        "浏览量中等，覆盖范围稳定。平均每条推文浏览量通常在数百到数千级别，处于KOL群体的中游水平（约30-60%分位），内容传播效果稳定，能够覆盖一定规模的受众，适合垂直领域的精准营销。",
        "浏览量较低，覆盖范围有限。平均每条推文浏览量通常在数十到数百级别，处于KOL群体的中下水平（约60-80%分位），内容传播范围相对有限，主要面向特定小规模受众群体，更适合小众领域的深度运营。",
        "浏览量很低，覆盖范围极小。平均每条推文浏览量通常在个位数到数十级别，处于KOL群体的后20%水平，内容传播范围非常有限，影响力较小，可能需要通过内容优化或平台运营来提升曝光度。"
    ]
    comment = get_default_comment(log_views, thresholds, comments)
    
    return (log_views, comment)

views_node = ScoreNode(
    key="views",
    name="Views",
    description="Content reach (log-transformed). Log transformation of views_count then normalized, allowing comparison of KOLs of different scales (from niche to mega-influencers).",
    weight=1.0,
    calc_raw=views_score
)

# 其他5个节点的中间节点（用于计算平均）
other_factors_node = ScoreNode(
    key="other_factors",
    name="Other Factors",
    description="Average of Originality, KOL Influence, Content Depth, Engagement, and Views",
    children=[
        originality_node,
        kol_influence_node,
        content_depth_node,
        engagement_node,
        views_node,
    ]
)

# 根节点
score_tree = ScoreNode(
    key="root",
    name="总分",
    description="KOL综合评分 = (其他5个因子的平均分) × Human Vitality",
    children=[
        other_factors_node,
        human_vitality_node,
    ]
)

