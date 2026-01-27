# KOL 评价报告生成器

一个完整的 Twitter KOL 评价系统，支持自动爬取 Twitter 数据、AI 评分分析和生成评价网页。

## 功能特性

- ✅ **自动爬取 Twitter 数据** - 通过 TweetScout API 抓取用户信息和推文
- ✅ **AI 评分分析** - 使用 GPT API 进行多维度评分（原创性、内容深度、人类活力等）
- ✅ **归一化参数管理** - 使用统一的归一化参数确保结果可比较
- ✅ **生成评价网页** - 自动生成美观的静态 HTML 报告

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置 API 密钥

```bash
# Linux/macOS
export TWEETSCOUT_API_KEY="your-tweetscout-key"
export OPENAI_API_KEY="your-openai-key"

# Windows PowerShell
$env:TWEETSCOUT_API_KEY="your-tweetscout-key"
$env:OPENAI_API_KEY="your-openai-key"
```

### 3. 修改用户名

编辑 `generate_report.py`，修改第 26 行的用户名：

```python
USERNAME = "elonmusk"  # 改成你要分析的用户名
```

### 4. 运行程序

```bash
python generate_report.py
```

### 5. 查看结果

程序运行完成后，打开 `static_html/index.html` 或 `static_html/user_0.html` 查看评价报告。

## 项目结构

```
KOL-Insight/
├── generate_report.py          # 主程序（整合所有功能）
├── twitter_crawler.py          # Twitter 爬虫模块
├── generate_static_html.py     # HTML 生成器
├── update_normalization.py     # 归一化参数更新脚本
├── requirements.txt            # 依赖文件
│
├── scoring/                    # 评分引擎
│   ├── engine.py               # 评分计算引擎
│   ├── schema.py               # 评分规则定义
│   └── normalization_manager.py # 归一化参数管理
│
├── models/                     # 数据模型
│   ├── data_model.py           # Account 和 Tweet 模型
│   └── score_node.py           # 评分节点结构
│
├── views/                      # HTML 模板
│   ├── view_scores.html        # 主页面模板
│   └── user_report.html       # 用户报告模板
│
├── utils.py                    # 工具函数（GPT API 调用）
│
├── data/                       # 数据目录
│   └── twitter_data.db         # 爬取的原始数据
│
├── outputs/                    # 输出目录
│   ├── normalization_params.json  # 归一化参数
│   ├── raw_scores_history.json    # 历史原始分数
│   ├── accounts.json              # 账号数据
│   ├── tweets.json                # 推文数据
│   ├── scores.json                # 评分数据
│   └── tree_structure.json        # 评分树结构
│
└── static_html/                # 生成的 HTML 网页
    ├── index.html              # 主页面
    └── user_0.html             # 用户详细报告
```

## 配置说明

在 `generate_report.py` 中可以修改以下配置：

```python
# 要分析的 Twitter 用户名（不含 @）
USERNAME = "elonmusk"

# 爬取配置
MAX_TWEETS = 50          # 每个用户最多爬取多少条推文
SKIP_COMMENTS = True     # 是否跳过评论（True 可以加快速度）

# 评分配置
TWEETS_LIMIT = 10        # 评分时每个账号只取前 N 条推文（防止 AI 调用过多）
```

## 评分维度

系统从以下 6 个维度对 KOL 进行评分：

1. **Originality（原创性）** - 评估内容的原创程度
2. **Human Vitality（人类活力）** - 检测机器人活动、假粉丝等
3. **KOL Influence（KOL 影响力）** - 评估在 KOL 社区中的认可度
4. **Content Depth（内容深度）** - 评估推文内容的深度和质量
5. **Engagement（参与度）** - 评估受众与内容的互动程度
6. **Views（浏览量）** - 评估内容的覆盖范围

**最终得分** = (其他5个因子的平均分) × Human Vitality

## 归一化参数管理

### 使用已有归一化参数

系统会自动从 `outputs/normalization_params.json` 加载归一化参数。如果没有该文件，会使用当前批次数据计算。

### 更新归一化参数

当积累了足够多的历史数据后，可以运行：

```bash
python update_normalization.py
```

这会基于所有历史原始分数重新计算 min/max 值，更新归一化参数。

### 原始分数保存

每次运行 `generate_report.py` 时，系统会自动：
- 保存原始分数到 `outputs/raw_scores_history.json`
- 使用已有的归一化参数进行归一化

## 工作流程

```
输入用户名 (USERNAME)
    ↓
[步骤 1] 爬取 Twitter 数据
    → 使用 twitter_crawler.py
    → 生成 data/twitter_data.db
    ↓
[步骤 2] 转换数据格式
    → 适配数据库结构
    → 转换为 Account/Tweet 对象
    ↓
[步骤 3] 计算评分
    → 加载归一化参数
    → 使用 AI 分析推文
    → 计算 6 个维度的评分
    → 保存原始分数到历史记录
    → 生成 outputs/scores.json
    ↓
[步骤 4] 生成评价网页
    → 生成静态 HTML 文件
    → 保存到 static_html/
    ↓
输出评价网页 ✅
```

## API 密钥获取

### TweetScout API

1. 访问 [TweetScout.io](https://tweetscout.io/)
2. 注册账户并选择合适的订阅计划
3. 在 API 设置中获取密钥

### OpenAI API

1. 访问 [OpenAI API Platform](https://platform.openai.com/api-keys)
2. 登录或注册账户
3. 点击 "Create new secret key"
4. 复制生成的密钥

## 注意事项

1. **API 费用**：评分功能需要调用 OpenAI API，会产生费用。建议先用 `TWEETS_LIMIT = 5` 测试。
2. **爬取速度**：抓取评论会显著增加时间和 API 调用次数，建议 `SKIP_COMMENTS = True`。
3. **数据限制**：为了避免过度消耗 API，默认只使用前 10 条推文进行评分。
4. **归一化参数**：首次运行如果没有归一化参数，会使用当前批次数据计算，可能导致不同批次结果不可比较。

## 故障排除

### 1. API 密钥错误

```
❌ 错误: 未设置 TWEETSCOUT_API_KEY 环境变量
```

**解决方法**：确保已设置环境变量。

### 2. 用户未找到

```
❌ 未能爬取到 xxx 的推文数据
```

**解决方法**：
- 检查用户名是否正确（不含 @）
- 确认该用户存在且可访问
- 检查 TweetScout API 是否正常

### 3. 评分失败

```
❌ 评分计算失败
```

**解决方法**：
- 检查 OpenAI API 密钥是否正确
- 检查账户余额是否充足
- 减少 `TWEETS_LIMIT` 的值

## 技术说明

### 评分计算流程

1. **叶节点原始分数计算**：对每个账号计算所有叶节点的原始分数
2. **叶节点归一化**：使用已有的归一化参数（或当前批次数据）进行 min-max 归一化
3. **非叶节点计算**：使用加权平均计算父节点得分
4. **根节点计算**：使用乘法规则：`总分 = other_factors × human_vitality`

### 归一化机制

- **叶节点归一化**：使用 min-max 归一化将原始分数映射到 0-1 区间
- **归一化参数**：保存在 `outputs/normalization_params.json`
- **历史数据**：每次计算的原始分数会自动保存到 `outputs/raw_scores_history.json`

### AI 功能

- **Human Vitality（人类活力）**：使用 GPT API 分析机器人活动
- **Content Depth（内容深度）**：使用 GPT API 评估内容深度
- **Root Comment（综合评语）**：使用 GPT API 生成账号的综合评语

这些功能会产生 API 费用。

### 异步计算

评分引擎支持异步并发计算，提高计算效率。叶节点分数计算和 AI 评语生成都是并发执行的。

## 修改评分规则

要想修改评分规则，需要编辑 `scoring/schema.py` 中的评分树结构，然后运行 `generate_report.py` 重新计算评分。

可以修改的内容包括：
- 添加/删除/修改叶节点
- 调整权重
- 修改归一化设置（`normalize` 属性）
- 修改评分函数（`calc_raw`）
- 调整树结构（添加中间节点）
- 修改根节点计算规则（当前是乘法规则）

**重要提示**：`outputs/tree_structure.json` 文件是根据 `schema.py` 自动生成的，不要直接修改该文件。

## 许可证

本项目遵循原项目的许可证。
