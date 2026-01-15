# 加密货币推文分析项目文档

## 项目概述

这是一个完整的加密货币KOL推文抓取和分析系统，能够自动识别社交媒体上的加密货币交易建议，并进行投资期限分析。

## 问题发现与解决

### 原始问题

在分析现有代码时发现，项目工作流程中缺失了一个关键环节：

- **输入**：`tweets.db`（推文数据库）
- **输出**：`guid_to_trade_tweet.db`（交易建议数据库）
- **缺失**：从推文中识别和提取交易建议的代码

### 分析结果

通过分析 `analyze_crypto_trends_concurrent.py` 的输入需求，确定缺失代码应该具备以下功能：

1. **推文分类**：判断推文是否包含加密货币交易建议
2. **信息提取**：提取推荐的加密货币名称和建议内容
3. **ID查找**：使用OpenAI API查找CoinGecko官方ID
4. **多币种处理**：一条推文涉及多个币种时分条存储
5. **容错处理**：未找到的币种标记为"NOT_FOUND"

## 完整工作流程

### 数据流图

```
KOL_yes.db 
    ↓ Step 1: create_kol_list.py
kol_list.json 
    ↓ Step 2: GetSeedKOL.py  
followingA.db 
    ↓ Step 3: KOLTweetCrawler.py
tweets.db 
    ↓ Step 4: generate_trade_tweets.py (新增)
guid_to_trade_tweet.db 
    ↓ Step 5: analyze_crypto_trends_concurrent.py
crypto_recommendations.db
```

### 各阶段说明

#### 阶段1：KOL列表准备

- **输入**：`KOL_yes.db` - 包含KOL用户名的数据库
- **处理**：`create_kol_list.py` - 从数据库读取用户名
- **输出**：`kol_list.json` - JSON格式的KOL列表

#### 阶段2：用户信息获取

- **输入**：`kol_list.json`
- **处理**：`GetSeedKOL.py` - 通过TweetScout API获取用户详细信息
- **输出**：`followingA.db` - 包含用户ID、头像、背景图等信息

#### 阶段3：推文抓取

- **输入**：`followingA.db`
- **处理**：`KOLTweetCrawler.py` - 抓取KOL的最新推文和评论
- **输出**：`tweets.db` - 原始推文数据

#### 阶段4：交易建议识别（新增）

- **输入**：`tweets.db`
- **处理**：`generate_trade_tweets.py` - 使用AI识别交易建议
- **输出**：`guid_to_trade_tweet.db` - 结构化的交易建议数据

#### 阶段5：投资期限分析

- **输入**：`guid_to_trade_tweet.db`
- **处理**：`analyze_crypto_trends_concurrent.py` - 分析投资期限和趋势
- **输出**：`crypto_recommendations.db` - 最终分析结果

## 新增代码详解

### generate_trade_tweets.py

**主要功能**：

1. 使用 `gpt-4o` 分类推文是否包含交易建议
2. 提取推文中的加密货币名称和建议内容
3. 使用 `gpt-4o-search-preview` 查找CoinGecko ID
4. 为每个币种创建独立记录

**关键特性**：

- **异步处理**：支持并发处理提高效率
- **多币种支持**：一条推文多个币种分别记录
- **智能分类**：AI判断交易建议的准确性
- **容错机制**：处理API错误和数据异常

**数据库结构**：

```sql
CREATE TABLE trade_tweets (
    guid TEXT PRIMARY KEY,           -- 全局唯一标识符
    tweet_id TEXT NOT NULL,         -- 推文ID
    author_id TEXT,                 -- 作者ID
    author_name TEXT,               -- 作者用户名
    full_text TEXT,                 -- 完整推文内容
    created_at TEXT,                -- 创建时间
    buy_what TEXT,                  -- 推荐的加密货币名称
    advice_content TEXT,            -- 交易建议内容
    coingecko_id TEXT,              -- CoinGecko官方ID
    has_trade_advice INTEGER,       -- 是否包含交易建议(0/1)
    processed_at TIMESTAMP          -- 处理时间
);
```

## 使用指南

### 环境准备

1. **Python依赖**：

```bash
pip install openai aiohttp asyncio sqlite3
```

1. **API密钥配置**：

```bash
export OPENAI_API_KEY='your-openai-api-key-here'
export TWEETSCOUT_API_KEY='your-tweetscout-api-key'
```

### 快速开始

#### 方法1：完整流程运行（推荐）
先准备输入文件，KOL_yes.db或者seed_user.json

```bash
# 设置API密钥
export OPENAI_API_KEY='your-key-here'

# 运行完整流程
chmod +x start.sh
dos2unix start.sh
./start.sh
```



#### 方法2：分步骤运行(不推荐)

1. **创建KOL列表**：

```bash
python3 create_kol_list.py --db KOL_yes.db --output kol_list.json --limit 100
```

1. **获取用户信息**：

```bash
python3 GetSeedKOL.py --input kol_list.json
```

1. **抓取推文**：

```bash
python3 KOLTweetCrawler.py --db_dir . --max_tweets 100 --max_concurrent_tasks 5
```

1. **识别交易建议**（新增步骤）：

```bash
python3 generate_trade_tweets.py --db_dir . --api_key $OPENAI_API_KEY --max_concurrent 10
```

1. **分析投资趋势**：

```bash
python3 analyze_crypto_trends_concurrent.py --db_dir . --api_key $OPENAI_API_KEY --max_concurrent 20
```

### 配置参数

#### start.sh 主要配置

```bash
KOL_DB_FILE="KOL_yes.db"        # 源KOL数据库
MAX_KOL_COUNT=100               # 最大KOL数量(0=无限制)
MAX_TWEETS=100                  # 每个KOL最大推文数
MAX_CONCURRENT_TASKS=5          # 并发任务数
```

#### generate_trade_tweets.py 参数

- `--db_dir`：数据库文件目录
- `--api_key`：OpenAI API密钥
- `--max_concurrent`：最大并发数（默认10）

#### analyze_crypto_trends_concurrent.py 参数

- `--db_dir`：数据库文件目录
- `--api_key`：OpenAI API密钥
- `--max_concurrent`：最大并发数（默认20）

## 输出文件说明

### 中间文件

- `kol_list.json` - KOL用户列表（含头像和背景图URL）
- `followingA.db` - KOL详细信息数据库
- `tweets.db` - 原始推文数据库
- `guid_to_trade_tweet.db` - 交易建议数据库

### 最终输出

- `crypto_recommendations.db` - 加密货币推荐分析结果

### 统计信息示例

```
🎉 完整流程执行完成！

📊 处理统计：
  • KOL数量: 100
  • 每个KOL最大推文数: 100  
  • 识别的交易建议: 1,250 条
  • 最终推荐记录: 2,100 条

📈 投资期限统计：
  short_term: 856 种币, 1,420 条
  long_term: 423 种币, 680 条

📈 热门币种 TOP10：
  Bitcoin (bitcoin) - 245 次
  Ethereum (ethereum) - 189 次
  Solana (solana) - 167 次
  ...
```

## 技术特点

### AI分析能力

- **智能分类**：准确识别交易建议vs普通讨论
- **多语言支持**：处理中英文混合内容
- **上下文理解**：理解隐含的投资建议

### 数据处理优势

- **异步并发**：大幅提升处理速度
- **错误恢复**：API限制和网络错误自动重试
- **增量处理**：避免重复处理相同数据
- **数据完整性**：事务处理确保数据一致性

### 扩展性设计

- **模块化架构**：各阶段独立，便于维护
- **配置灵活**：支持自定义参数调整
- **日志完整**：详细的处理日志便于调试
- **备份机制**：自动备份原有数据

## 故障排除

### 常见问题

1. **API限制**：
	- 现象：429错误频繁出现
	- 解决：降低 `max_concurrent` 参数
2. **内存不足**：
	- 现象：处理大量数据时系统卡顿
	- 解决：分批处理，减少并发数
3. **数据库锁定**：
	- 现象：SQLite database is locked
	- 解决：检查是否有其他程序占用数据库
4. **API密钥错误**：
	- 现象：认证失败
	- 解决：检查环境变量设置

### 日志位置

- 主日志：`logs/trade_tweet_generator_YYYYMMDD_HHMMSS.log`
- 其他日志：各脚本目录下的 `.log` 文件

## 后续优化建议

1. **性能优化**：
	- 实现智能缓存机制
	- 优化数据库查询
	- 增加批量处理能力
2. **功能扩展**：
	- 支持更多社交平台
	- 增加情感分析
	- 实现实时监控
3. **数据质量**：
	- 改进AI分类准确率
	- 增加人工审核流程
	- 实现反馈学习机制

------

**创建时间**：2025年11月13日
 **版本**：v1.3
 **维护者**：Naseele