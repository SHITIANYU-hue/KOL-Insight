# KOL Report（推文抓取 → 交易建议识别 → 趋势分析 → HTML 报告）

这是一个面向加密货币 KOL 的端到端分析项目：

1. 从指定 KOL 抓取推文（可选抓评论）
2. 用 OpenAI 识别推文中的“交易建议”，并结构化落库
3. 基于结构化数据生成 `crypto_recommendations.db`
4. 进一步做「KOL × 币种」深度分析 + CoinGecko 真实价格验证
5. 输出可交互的专业级 HTML 报告站点（汇总页 / KOL 页 / 币种页）

本项目需要fullprogress2产出的KOL_yes.db，或者自备seed_user.json

## 项目结构

- `01spider_module/`：抓取与初步结构化（入口：`01spider_module/start.sh`）
  - 模块说明：`01spider_module/README.md`
- `02analyze_module/`：读取产出并生成报告（入口：`02analyze_module/refined_v2.py`）
  - 模块说明：`02analyze_module/Readme.md`
- `data/`：推荐作为跨模块的数据交换与最终产物目录
  - `01spider_module/start.sh` 默认会把关键产物复制到这里（可配置）

## 数据流（端到端）

```
KOL_yes.db / seed_user.json
  → (01) kol_list.json
  → (01) followingA.db
  → (01) tweets.db
  → (01) guid_to_trade_tweet.db
  → (01) crypto_recommendations.db
  → (02) enhanced_kol_reports_v2_optimized/ (HTML 报告站点)
```

## 环境与依赖

### 运行方式建议

- `01spider_module/start.sh` 是 `bash` 脚本，建议在以下环境运行：
  - Linux/macOS
  - Windows：WSL 或 Git Bash（推荐 WSL）
- `02analyze_module/refined_v2.py` 为 Python 脚本（Windows/WSL/Linux/macOS 均可）

### Python 版本

- 建议 `Python 3.9+`

### Python 依赖（按代码实际使用）

项目未提供统一的 `requirements.txt`，你可以按需安装：

```bash
pip install openai aiohttp requests pandas numpy matplotlib
```

> 注：`01spider_module` 的推文抓取依赖 TweetScout API；`02analyze_module` 会访问 CoinGecko（免费或 Pro）并可能下载头像/背景图 URL。

## API Key 配置

### 必需

- OpenAI：`OPENAI_API_KEY`

### 建议

- TweetScout：`TWEETSCOUT_API_KEY`（用于抓取用户信息/推文）
- CoinGecko Pro：`COINGECKO_API_KEY`（可选；没有也能跑，但验证/数据质量可能受限）

更多密钥说明参考：`01spider_module/spider_module_api.md`

## 快速开始（推荐：先跑 01，再跑 02）

### Step 0：准备 key

Linux/macOS/WSL（bash）：

```bash
export OPENAI_API_KEY="your-openai-key"
export TWEETSCOUT_API_KEY="your-tweetscout-key"
```

Windows PowerShell：

```powershell
$env:OPENAI_API_KEY="your-openai-key"
$env:TWEETSCOUT_API_KEY="your-tweetscout-key"
```



格式预处理：

dos2unix 01spider_module/[start.sh](http://start.sh)

文件权限修正：

sudo chmod +x 01spider_module/[start.sh](http://start.sh)



### Step 1：运行抓取与初步结构化（01spider_module）

在 `01spider_module` 目录下执行：

```bash
cd 01spider_module
dos2unix start.sh  # 如果提示换行符问题
chmod +x start.sh
./start.sh
```

运行过程会交互式询问：

- KOL 列表来源：
  - `1)` 从 `KOL_yes.db` 生成 `kol_list.json`
  - `2)` 使用外部 JSON（默认 `seed_user.json`）
- 是否抓取评论：`y/N`

默认情况下，脚本会在结束时把关键产物复制到项目根目录 `data/`：

- `data/crypto_recommendations.db`
- `data/kol_list.json`

可通过环境变量控制复制行为（在执行 `./start.sh` 前设置）：

- `COPY_OUTPUTS=1`：复制（默认）
- `COPY_OUTPUTS=0`：不复制
- `OUTPUT_DATA_DIR=../data`：目标目录（默认 `../data`，即项目根 `data/`）

### Step 2：生成 HTML 报告（02analyze_module）

在 `02analyze_module` 目录下执行（假设 Step 1 已生成 `data/crypto_recommendations.db`）：

```bash
cd 02analyze_module
python3 refined_v2.py --db_dir ../data --api_key "your-openai-key" --coingecko_api_key "your-coingecko-key"
```

如果你没有 CoinGecko Pro Key，建议显式使用免费接口：

```bash
python3 refined_v2.py --db_dir ../data --api_key "your-openai-key" --coingecko_api_key ""
```

想先小规模跑通（省时省钱）：

```bash
python3 refined_v2.py --db_dir ../data --api_key "your-openai-key" --limit 3
```

完成后打开报告入口：

- `data/enhanced_kol_reports_v2_optimized/index.html`

## 输入/输出说明（全局视角）

### 输入

- `01spider_module/KOL_yes.db`：KOL 用户名源数据库（可选，如果走数据库生成）
- `01spider_module/seed_user.json`：外部 KOL 列表示例（可选，如果走外部 JSON）
- `data/crypto_recommendations.db`：`02analyze_module` 的核心输入（来自 01 的最后一步）
- `data/kol_list.json`：建议提供（用于报告中的头像/背景图展示；若存在则会尝试下载并缓存到报告目录）

### 输出（关键产物）

01 模块（默认在 `01spider_module/` 生成，部分会复制到 `data/`）：

- `kol_list.json`、`followingA.db`、`tweets.db`、`guid_to_trade_tweet.db`、`crypto_recommendations.db`

02 模块（在 `--db_dir` 下生成）：

- `enhanced_kol_reports_v2_optimized/`（HTML 报告站点 + JSON/图表/日志/图片资源）

## 常见问题

### 1）Windows 直接运行 `start.sh` 报错

`start.sh` 依赖 `bash/chmod/rm/mv/cp` 等命令。推荐改用 WSL 或 Git Bash 来运行 `01spider_module`。

### 2）找不到 `crypto_recommendations.db`

确认：

- `01spider_module/start.sh` 已跑完，且未把 `COPY_OUTPUTS` 设为 `0`
- `data/crypto_recommendations.db` 存在
- `02analyze_module/refined_v2.py` 的 `--db_dir` 指向正确目录（该目录下必须有 `crypto_recommendations.db`）

### 3）报告里头像/背景图不显示

报告生成器会从 `kol_list.json` 中的 URL 下载图片到：

- `.../enhanced_kol_reports_v2_optimized/assets/images/`

需要网络可访问图片 URL，且 URL 本身有效。

### 4）429 / 超时 / 运行很慢

- 先用 `--limit 3` 跑通流程
- 不要一开始就开 `--parallel_chains`
- 如仍受限，考虑降低脚本内部并发（见 `02analyze_module/refined_v2.py` 中 `max_concurrent_tweet_analysis` 等配置）

## 模块细分说明

- 01 模块详细说明：`01spider_module/README.md`
- 02 模块详细说明：`02analyze_module/Readme.md`
- API Key 说明：`01spider_module/spider_module_api.md`
