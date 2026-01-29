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
        return (0.0, "No tweet data")
    
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
    comment = f"{comment} (Original tweets: {original_count}/{total_tweets}, Ratio: {originality_ratio:.2f})"
    
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
        return (0.0, "No tweet data")
    
    # Calculate views/follower ratio
    total_views = sum(t.views_count for t in account.tweets if t.views_count)
    avg_views_per_tweet = total_views / len(account.tweets) if account.tweets else 0
    views_follower_ratio = avg_views_per_tweet / account.followers_count if account.followers_count > 0 else 0
    
    # Calculate engagement rate
    total_interactions = sum(t.likes_count + t.retweets_count + t.replies_count for t in account.tweets)
    engagement_rate = total_interactions / total_views if total_views > 0 else 0
    
    # Use LLM to evaluate bot activity
    tweets_text = account.get_tweets_text()
    json_schema = {
        "bot_score": "Bot activity score, integer 0-100, higher means more bot activity",
        "anomaly_detection": "Anomaly detection results, describing discovered abnormal patterns",
        "comment": "Comment, briefly describing bot activity situation"
    }
    prompt = f"""Please evaluate the authenticity of interactions for this account. Analyze the following metrics:
- Average views per tweet / followers ratio: {views_follower_ratio:.4f}
- Average engagement rate (likes + retweets + replies) / views: {engagement_rate:.4f}
- Followers count: {account.followers_count}
- Tweet count: {len(account.tweets)}

Tweet content:
{tweets_text}

Please evaluate if there are bot activities, fake followers, engagement manipulation, or other anomalies. Provide a bot activity score (0-100), where higher scores indicate more bot activity and lower authenticity. Then convert to authenticity score (100 - bot_score). Don't be too strict in scoring; if there's no obvious bot activity, you can respond with around 70 points. Please respond in JSON format and use English for all comments."""
    
    result = await call_gpt(prompt, json_schema)
    bot_score = float(result.get("bot_score", 70))
    authenticity_score = (100 - bot_score) / 100
    comment = result.get("comment", "")
    print(f"Human authenticity score: {authenticity_score}")
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
        return (0.0, "No KOL connection data")
    
    # 返回原始值，归一化在engine中完成
    comment = f"KOL connections: {friends_count}"
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
        return (0.0, "No tweet content")
    
    # Use LLM to evaluate content depth of each tweet
    tweets_text = "\n\n".join([f"Tweet {i+1}: {t.full_text}" for i, t in enumerate(account.tweets)])
    json_schema = {
        "tweets": [{"index": "Tweet index (starting from 1)", "depth_score": "Content depth score, integer 0-100, higher means deeper content"}],
        "comment": "Comment, briefly describing content depth situation"
    }
    result = await call_gpt(f"Please evaluate the content depth of each tweet. Content depth includes: depth of analysis, quality of insights, information value provided, etc. Give each tweet a depth score (0-100), where higher scores indicate deeper and more insightful content. Please respond in JSON format and use English for all comments.\n\nTweet content:\n\n{tweets_text}", json_schema)
    
    depth_scores = []
    for item in result.get("tweets", []):
        depth_scores.append(float(item.get("depth_score", 0)))
    
    if not depth_scores:
        return (0.0, "Unable to evaluate content depth")
    
    avg_depth = sum(depth_scores) / len(depth_scores)
    comment = result.get("comment", f"Average content depth: {avg_depth:.2f}")
    print(f"Content depth score: {avg_depth}")
    return (avg_depth / 100.0, comment) # Normalize to 0-1

content_depth_node = ScoreNode(
    key="content_depth",
    name="Content Depth",
    description="Content analysis depth and quality. Calculated as the average depth score (depth_score) across all tweets, reflecting overall content quality.",
    weight=1.0,
    calc_raw=content_depth_score,
    normalize=False
)

# 5. Engagement - 参与度
def engagement_score(account: Account):
    if not account.tweets:
        return (0.0, "No tweet data")
    
    total_interactions = sum(t.likes_count + t.retweets_count + t.replies_count for t in account.tweets)
    total_views = sum(t.views_count for t in account.tweets if t.views_count)
    
    if total_views == 0:
        return (0.0, "No view count data")
    
    engagement_rate = total_interactions / total_views
    
    # 转换为0-100分数（假设正常互动率在0.01-0.1之间，超过0.1算很高）
    # 这里直接返回原始比例，归一化会在engine中完成
    score = engagement_rate * 1000  # 放大以便区分
    
    thresholds = [0.08, 0.06, 0.04, 0.02]
    comments = [
        "Extremely high engagement, active audience interaction",
        "Good engagement, moderate audience interaction",
        "Average engagement",
        "Low engagement",
        "Very low engagement"
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
        return (0.0, "No tweet data")
    
    total_views = sum(t.views_count for t in account.tweets if t.views_count)
    avg_views = total_views / len(account.tweets) if account.tweets else 0
    
    if avg_views <= 0:
        return (0.0, "No view count data")
    
    # 对数变换
    log_views = math.log(avg_views + 1)
    
    # 返回对数变换后的值，归一化会在engine中完成
    # thresholds基于对数变换后的值，分布情况：典型KOL范围约在5.5-9.5之间
    # log(1000+1)≈6.9, log(10000+1)≈9.2, log(100000+1)≈11.5
    thresholds = [8.5, 7.5, 6.5, 5.5]
    comments = [
        "Extremely high views with broad reach. Average views per tweet typically in the tens of thousands, ranking in the top 10-15% of KOLs, demonstrating strong content dissemination and influence, capable of reaching large target audiences, suitable for brand promotion and large-scale marketing campaigns.",
        "High views with good reach. Average views per tweet typically in the thousands to tens of thousands, ranking in the top 30-40% of KOLs, good content dissemination effectiveness, capable of effectively reaching target audience groups, with certain brand promotion value.",
        "Moderate views with stable reach. Average views per tweet typically in the hundreds to thousands, ranking in the middle tier of KOLs (approximately 30-60th percentile), stable content dissemination effectiveness, capable of covering a certain scale of audience, suitable for vertical field precision marketing.",
        "Low views with limited reach. Average views per tweet typically in the tens to hundreds, ranking in the lower-middle tier of KOLs (approximately 60-80th percentile), relatively limited content dissemination range, mainly targeting specific small-scale audience groups, more suitable for niche field deep operations.",
        "Very low views with minimal reach. Average views per tweet typically in single digits to tens, ranking in the bottom 20% of KOLs, very limited content dissemination range, small influence, may need to improve exposure through content optimization or platform operations."
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

