# 01spider_module（推文抓取 & 交易建议/趋势分析）

该模块用于从指定加密货币 KOL 抓取推文（可选抓评论），用 OpenAI 识别“交易建议”，并进一步分析投资期限/趋势，最终产出结构化 SQLite 数据库供后续分析使用。模块入口为 `start.sh`。

## 功能概览（数据流）

`KOL_yes.db`/`seed_user.json` → `kol_list.json` → `followingA.db` → `tweets.db` → `guid_to_trade_tweet.db` → `crypto_recommendations.db`

对应脚本：

1. `create_kol_list.py`：从 `KOL_yes.db` 读取用户名，生成 `kol_list.json`
2. `GetSeedKOL.py`：通过 TweetScout API 获取用户信息，生成 `followingA.db`（并导出含头像/背景的 `kol_list.json`）
3. `KOLTweetCrawler.py`：抓取推文（可选抓评论），生成 `tweets.db`
4. `generate_trade_tweets.py`：用 OpenAI 识别交易建议，生成 `guid_to_trade_tweet.db`
5. `analyze_crypto_trends_concurrent.py`：分析投资期限/趋势，生成 `crypto_recommendations.db`

## 运行环境

- 建议在 Linux/macOS/WSL/Git Bash 下运行（`start.sh` 使用了 `bash`、`chmod`、`rm/mv/cp` 等命令）
- Python：建议 `3.9+`
- 依赖包（按脚本使用情况）：`openai`、`aiohttp`、`requests`
- 网络：需要访问 TweetScout API 与 OpenAI API

## API Key

- `OPENAI_API_KEY`：必需（`start.sh` 会检查）
- `TWEETSCOUT_API_KEY`：建议设置（用于抓取用户信息/推文）

项目内有一份更完整的密钥说明：`spider_module_api.md`。

## 快速开始（推荐：跑完整流程）

在 `01spider_module` 目录下执行：

```bash
export OPENAI_API_KEY="your-openai-key"
export TWEETSCOUT_API_KEY="your-tweetscout-key"

dos2unix start.sh  # 如果提示换行符问题
chmod +x start.sh
./start.sh
```

运行过程中会交互式询问：

- KOL 列表来源：`1)` 从 `KOL_yes.db` 生成，或 `2)` 使用外部 JSON（默认 `seed_user.json`）
- 是否抓取评论：`y/N`（抓评论会更慢，且 API 调用更多）

## 输入说明

### 方式 A：从数据库生成 KOL 列表

- 输入：`KOL_yes.db`
- 输出：`kol_list.json`（形如：`[{ "username": "xxx" }, ... ]`）

可通过 `start.sh` 内的 `MAX_KOL_COUNT` 限制最多读取多少个 KOL（`0` 表示不限制）。

### 方式 B：使用外部 JSON

外部 JSON 必须满足：

- 最外层为数组
- 每项为对象，且至少包含 `username` 字段

示例：`01spider_module/seed_user.json`

## 输出产物

所有数据库默认生成在 `01spider_module` 当前目录：

- `kol_list.json`：KOL 列表（Step 3 后会补充 `avatar/background`）
- `followingA.db`：KOL 用户信息（TweetScout）
- `tweets.db`：推文与（可选）评论
- `guid_to_trade_tweet.db`：从推文中识别出的“交易建议”
- `crypto_recommendations.db`：按币种 + 投资期限（short/long term）汇总的分析结果
- `logs/`：`generate_trade_tweets.py`、`analyze_crypto_trends_concurrent.py` 运行日志

`start.sh` 末尾会按需复制最终产物到上一级 `data/`（默认开启）：

- `COPY_OUTPUTS=1`：复制（默认）
- `COPY_OUTPUTS=0`：不复制
- `OUTPUT_DATA_DIR=../data`：目标目录（可自定义）

## 分步运行（调试用）

```bash
python3 create_kol_list.py --db KOL_yes.db --output kol_list.json --limit 10
python3 GetSeedKOL.py --input kol_list.json
python3 KOLTweetCrawler.py --db_dir . --max_tweets 25 --max_concurrent_tasks 5 --skip_comments
python3 generate_trade_tweets.py --db_dir . --api_key "$OPENAI_API_KEY" --max_concurrent 5 --blacklist crypto_blacklist.txt
python3 analyze_crypto_trends_concurrent.py --db_dir . --api_key "$OPENAI_API_KEY" --max_concurrent 10
```

## 备注与常见问题

- `start.sh` 会对已存在的数据库做时间戳备份（`.bak`），避免覆盖丢数据。
- `generate_trade_tweets.py` 支持黑名单：`crypto_blacklist.txt`（用于过滤泛化词如 `defi`、`perp` 等）。
- 若你在 Windows 直接运行 `start.sh` 遇到命令缺失，建议用 WSL 或 Git Bash。
- 模块更详细的背景与流程说明见：`spider_module.md`。
