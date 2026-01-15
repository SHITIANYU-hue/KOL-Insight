# 02analyze_module（基于 01spider_module 产出生成分析报告）

该模块以 `01spider_module` 产出的 `crypto_recommendations.db`（以及可选的 `kol_list.json`）为输入，按「KOL × 币种」聚合推文链路，调用 OpenAI + CoinGecko 做深度分析与真实价格验证，最后生成可交互的专业级 HTML 报告。

入口文件：`refined_v2.py`

## 输入文件（来自 01spider_module）

必需：

- `crypto_recommendations.db`
  - 默认放在你传入的 `--db_dir` 下（例如 `../data/crypto_recommendations.db`）
  - 表：`crypto_recommendations`
  - `refined_v2.py` 会读取这些字段：
    - `tweet_id`, `author_id`, `author_name`, `tweet_created_at`
    - `crypto_name`, `coingecko_id`, `full_tweet_text`, `investment_horizon`
  - 会过滤掉 `coingecko_id` 为 `NOT_FOUND/ERROR/空值` 的记录，以及 `tweet_created_at` 为空的记录

强烈建议（用于头像/背景图与更好的展示）：

- `kol_list.json`
  - `refined_v2.py` 与 `html_generator.py` 会尝试在多个位置查找（优先 `--db_dir`，其次上一级 `data/` 等）
  - 结构示例（字段可选，但 `username` 必需）：
    - `[{ "username": "xxx", "avatar": "https://...", "background": "https://..." }]`

## 输出内容（报告目录结构）

脚本会在 `--db_dir` 下生成：`enhanced_kol_reports_v2_optimized/`

- `enhanced_kol_reports_v2_optimized/index.html`：汇总首页（KOL 列表）
- `enhanced_kol_reports_v2_optimized/kol_reports/<kol>_analysis.html`：单个 KOL 的币种总览页
- `enhanced_kol_reports_v2_optimized/coin_reports/<kol>_<coin>_analysis.html`：单个「KOL × 币种」深度页（含图表 + hotpoint 交互）
- `enhanced_kol_reports_v2_optimized/kol_analysis/*.json`：每条链路的结构化分析结果（便于二次开发/排查）
- `enhanced_kol_reports_v2_optimized/charts/*.png`：链路图表输出（同时也会在 HTML 中以 base64 内嵌展示）
- `enhanced_kol_reports_v2_optimized/assets/images/*`：从 `kol_list.json` 下载的头像/背景图（需要网络）
- `enhanced_kol_reports_v2_optimized/analyzer_v2_optimized_*.log`：运行日志

## 依赖与环境

- Python：建议 `3.9+`
- 主要依赖：`openai`、`requests`、`pandas`、`numpy`、`matplotlib`
- 网络：需要访问 OpenAI API；如启用真实价格验证/FDV 过滤/图片下载，需要访问 CoinGecko 与图片 URL
- 字体：脚本会尝试启用 CJK 字体（未找到会自动回退）；如果图表中文乱码，建议安装 `Noto Serif CJK` 或其他中文字体

## API Key

- OpenAI：通过 CLI 参数 `--api_key` 传入（必需）
- CoinGecko：通过 `--coingecko_api_key` 传入（可选）
  - 注意：`refined_v2.py` 里该参数有默认值；如果你没有 Pro Key，建议显式传空字符串使用免费接口：`--coingecko_api_key ""`

## 快速开始

在 `02analyze_module` 目录下执行（示例假设 `../data/crypto_recommendations.db` 已存在）：

```bash
python3 refined_v2.py --db_dir ../data --api_key "你的OPENAI_API_KEY" --coingecko_api_key "你的COINGECKO_KEY"
```

仅跑少量链路做冒烟测试（省时省钱）：

```bash
python3 refined_v2.py --db_dir ../data --api_key "你的OPENAI_API_KEY" --limit 3
```

链路级并行（会叠加推文级并发，容易打到限速；建议先小规模验证）：

```bash
python3 refined_v2.py --db_dir ../data --api_key "你的OPENAI_API_KEY" --parallel_chains
```

运行完成后打开：

- `../data/enhanced_kol_reports_v2_optimized/index.html`

## 命令行参数

- `--db_dir`：输入/输出目录（必须存在，且该目录下必须有 `crypto_recommendations.db`）
- `--api_key`：OpenAI API Key（必需）
- `--coingecko_api_key`：CoinGecko Pro Key（可选；传空字符串可走免费 API）
- `--limit`：限制分析的「推理链（KOL×币种）」数量（用于测试）
- `--verbose`：更详细日志
- `--parallel_chains`：链路级并行分析（更快但更容易触发限速/费用更高）

## 逻辑摘要（做了什么）

`refined_v2.py` 核心流程：

1. 读取 `crypto_recommendations.db`，按 `author_name + crypto_name` 聚合为「推理链」
2. 过滤明显无效资产（法币、稳定币、部分传统资产等）
3. 可选：通过 CoinGecko 查询 FDV，过滤 FDV 明确低于 $1,000,000 的币，减少无效开销
4. 对链路内推文做分阶段 AI 分析（包含“推文质量深度评估：好/坏”）
5. 拉取 CoinGecko 历史价格做真实验证（修复时间戳/422 等问题的容错流程）
6. 生成优化图表与 hotpoint 坐标数据
7. 调用 `html_generator.py` 生成完整站点：`index.html` + KOL 页 + 币种页（并下载头像/背景图）

## 已知修复：用户名含下划线导致解析错误

历史上 `load_reasoning_chains()` 用单下划线拼接 `author_name` 与 `crypto_name`：

- 旧：`chain_key = f"{author_name}_{crypto_name}"`
- 当用户名本身含 `_`（例如 `DeFi_Bean`）会导致后续解析把用户名切开，币名被污染

当前版本改用专用分隔符并保留兼容：

- 新：`chain_key = f"{author_name}|||{crypto_name}"`
- 解析时先 `split('|||', 1)`，如果不存在再回退 `split('_', 1)`

## 常见问题

1. 提示找不到 `crypto_recommendations.db`
   - 确认 `--db_dir` 目录存在，且该目录下有 `crypto_recommendations.db`
2. 提示找不到 `kol_list.json`
   - 不影响核心分析，但头像/背景图等展示会缺失；建议将 `kol_list.json` 放在 `--db_dir` 或上一级 `data/`
3. 报告生成了但图片/背景没有
   - HTML 生成器会从 URL 下载图片，需要网络；也可能是 URL 失效或被限流
4. 频繁 429 / 超时 / 速度慢
   - 先用 `--limit` 小规模跑通；再考虑是否开启 `--parallel_chains`；必要时降低并发（脚本内 `max_concurrent_tweet_analysis` 等参数）
