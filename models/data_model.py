from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class Tweet:
    tweet_id: str
    author_id: str
    full_text: str
    likes_count: Optional[int] = 0
    retweets_count: Optional[int] = 0
    replies_count: Optional[int] = 0
    views_count: Optional[int] = 0
    in_reply_to_status_id_str: Optional[str] = None
    is_quote_status: Optional[int] = 0
    
@dataclass
class Account:
    user_id: str
    username: Optional[str] = '无名大侠'
    description: Optional[str] = '这个人很写，什么也没有懒'
    followers_count: Optional[int] = 0
    friends_count: Optional[int] = 0
    tweets_count: Optional[int] = 0
    tweets: Optional[List[Tweet]] = field(default_factory=list)
    #register_date: Optional[str] = '2025-01-01'

    def get_tweets_text(self) -> str:
        # 确保所有 full_text 都是字符串，过滤掉 None 和空值
        texts = []
        for tweet in self.tweets:
            if tweet and hasattr(tweet, 'full_text'):
                text = str(tweet.full_text) if tweet.full_text is not None else ""
                if text:
                    texts.append(text)
        return "\n\n".join(texts)
