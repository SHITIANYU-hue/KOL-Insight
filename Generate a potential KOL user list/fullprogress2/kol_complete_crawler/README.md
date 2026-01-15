# KOL 完整爬虫

这是一个用于爬取KOL(Key Opinion Leader)推文和评论的工具。程序从指定的KOL_yes.db文件中读取用户信息，然后爬取每个用户的推文和评论数据，并保存到KOL_tweets.db数据库中。

## 功能特点

- 从KOL_yes.db读取用户信息
- 爬取用户的推文数据
- `爬取推文的评论数据（可选）
- 支持限制每用户最大推文数和每推文最大评论数
- 多任务并发爬取，提高效率
- 智能请求限速，避免API限制
- 批量数据处理和提交
- 详细的日志记录和统计信息

## 使用方法

### 1. 基本使用（爬取全部数据）

```bash
# 使用默认并发设置
python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --max_tweets 0 --max_comments_per_tweet 0
# 如果db文件在当前目录，则可以简写为：python kol_complete_crawler.py --kol_db_path "KOL_yes.db" --max_tweets 0 --max_comments_per_tweet 0 下同
# 自定义并发设置
python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --max_tweets 0 --max_comments_per_tweet 0 --max_tweet_tasks 25 --max_comment_tasks 20
```

### 2. 限制数量爬取

```bash
# 使用默认并发设置
python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --max_tweets 100 --max_comments_per_tweet 50

# 自定义并发设置
python3 kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --max_tweets 100 --max_comments_per_tweet 50 --max_tweet_tasks 25 --max_comment_tasks 20
```

### 3. 只爬取推文，不爬取评论

```bash
# 使用默认并发设置
python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --no_comments

# 由于不爬取评论，可提高推文爬取并发
python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --no_comments --max_tweet_tasks 40
```

### 4. 查看统计信息

```bash
python kol_complete_crawler.py --kol_db_path "完整路径/KOL_yes.db" --stats_only
```

## 性能优化

本工具经过多项性能优化，以提高爬取速度和稳定性：

1. **智能请求限速**
   - 使用RateLimiter控制API请求速率
   - 自动调整请求速率，避免触发API限制

2. **并发处理**
   - 推文和评论采用异步并发处理
   - 默认推文并发数为25，评论并发数为20
   - 可通过命令行参数调整并发数量

3. **数据库优化**
   - 批量提交数据，减少IO操作
   - 优化SQLite设置，提高写入性能

4. **智能过滤**
   - 对超大评论数量的热门推文进行智能处理
   - 避免在低价值内容上浪费时间

## 参数说明

- `--kol_db_path`: **必需**，KOL_yes.db文件的完整路径
- `--max_tweets`: 每用户最大推文数，0表示全部
- `--max_comments_per_tweet`: 每推文最大评论数，0表示全部
- `--collect_comments`: 是否收集评论
- `--no_comments`: 不收集评论，覆盖`collect_comments`设置
- `--max_tweet_tasks`: 推文爬取的并发任务数，默认25
- `--max_comment_tasks`: 评论爬取的并发任务数，默认20
- `--api_key`: TweetScout API密钥
- `--stats_only`: 仅显示统计信息，不进行爬取

## 数据库结构

### KOL_tweets.db

#### 表: tweets
- `id`: 自增主键
- `tweet_id`: 推文ID (唯一)
- `conversation_id`: 对话ID
- `author_id`: 作者ID
- `author_name`: 作者名称
- `full_text`: 推文内容
- `created_at`: 创建时间
- `likes_count`: 点赞数
- `retweets_count`: 转发数
- `replies_count`: 回复数
- `views_count`: 查看数
- `collected_at`: 收集时间

#### 表: comments
- `id`: 自增主键
- `tweet_id`: 关联的推文ID
- `comment_id`: 评论ID (唯一)
- `author_id`: 评论作者ID
- `author_name`: 评论作者名称
- `comment_text`: 评论内容
- `created_at`: 创建时间
- `likes_count`: 点赞数
- `collected_at`: 收集时间

#### 表: processing_log
- `id`: 自增主键
- `user_id`: 用户ID (唯一)
- `username`: 用户名
- `tweets_collected`: 已收集推文数
- `comments_collected`: 已收集评论数
- `last_processed`: 最后处理时间
- `status`: 处理状态

## 错误处理

- 程序内置重试机制，可以应对网络波动和API限制
- 对每个用户的处理独立进行，单个用户失败不会影响整体流程
- 详细的日志记录，便于问题定位和排查 