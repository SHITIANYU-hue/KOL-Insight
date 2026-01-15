#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  start.sh — 完整的推文抓取和分析脚本 · 2025-04
# -----------------------------------------------------------------------------
#  步骤
#   1) 从数据库文件读取KOL列表并创建kol_list.json
#   2) 抓取指定KOL的推文 → tweets.db
#   3) 从推文中识别交易建议 → guid_to_trade_tweet.db
#   4) 分析加密货币趋势 → crypto_recommendations.db
# -----------------------------------------------------------------------------
# 如果报错请先执行dos2unix start.sh
# 如果dos2unix command not found，请先安装dos2unix
set -euo pipefail

# 配置变量
KOL_DB_FILE="KOL_yes.db"
KOL_LIST_FILE="kol_list.json"
MAX_KOL_COUNT=10           # 从数据库最多读取多少个KOL用户 (设为0表示读取全部)
MAX_TWEETS=25
MAX_CONCURRENT_TASKS=5
OPENAI_API_KEY="${OPENAI_API_KEY:-}"  # 从环境变量读取，或手动设置
# 是否将最终输出复制到上一级 data 目录（默认 1 = 复制，设置为0可跳过复制）
COPY_OUTPUTS="${COPY_OUTPUTS:-1}"
# 可通过环境变量指定目标目录（默认 ../data）
OUTPUT_DATA_DIR="${OUTPUT_DATA_DIR:-../data}"

# 检查API密钥
if [[ -z "$OPENAI_API_KEY" ]]; then
    echo "❌ 请设置 OPENAI_API_KEY 环境变量"
    echo "   export OPENAI_API_KEY='your-api-key-here'"
    echo "   或者直接在脚本中设置 OPENAI_API_KEY 变量"
    exit 1
fi

# ╭──────────────── 创建KOL列表（可交互选择） ─────────────╮
echo -e "\n[Step 1] 选择 KOL 列表的来源..."

echo "1) 从数据库创建 KOL 列表（使用 create_kol_list.py，默认）"
echo "2) 使用已有的 JSON 文件（将复制为 $KOL_LIST_FILE）"
read -n1 -p "请选择 1 或 2（默认 1）: " KOL_SOURCE
echo

if [[ "$KOL_SOURCE" == "2" ]]; then
    # 使用外部 JSON 文件
    DEFAULT_EXTERNAL_JSON="seed_user.json"
    read -r -p "请输入外部 JSON 文件路径（例如 /path/to/file.json，回车使用默认: $DEFAULT_EXTERNAL_JSON）: " EXTERNAL_JSON

    if [[ -z "$EXTERNAL_JSON" ]]; then
        EXTERNAL_JSON="$DEFAULT_EXTERNAL_JSON"
        echo "ℹ️ 使用默认外部 JSON: $EXTERNAL_JSON"
    fi

    if [[ ! -f "$EXTERNAL_JSON" ]]; then
        echo "❌ 指定的文件不存在: $EXTERNAL_JSON"
        echo "   请确保文件路径正确，或先创建一个名为 $DEFAULT_EXTERNAL_JSON 的文件。"
        exit 1
    fi

    # 验证 JSON 格式（使用 python 检查：必须是数组，且每项为对象并包含 username 字段）
    if ! python3 - <<PYTHON
import sys, json
path = r"$EXTERNAL_JSON"
try:
    data = json.load(open(path, encoding='utf-8'))
except Exception as e:
    print(f"❌ JSON 文件解析失败: {e}")
    sys.exit(2)

if not isinstance(data, list):
    print(f"❌ JSON 格式错误: 预期最外层为数组 (list)，但解析得到 {type(data).__name__}")
    sys.exit(2)

for i, item in enumerate(data, 1):
    if not isinstance(item, dict):
        print(f"❌ 第 {i} 项不是对象 (dict)：{item}")
        sys.exit(2)
    if 'username' not in item:
        print(f"❌ 第 {i} 项缺少 'username' 字段：{item}")
        sys.exit(2)

sys.exit(0)
PYTHON
    then
        echo "❌ JSON 校验失败。请将 JSON 格式调整为下述示例后再重试："
        cat <<'EXAMPLE'
示例 JSON (数组形式，每项为对象且包含 "username" 字段):
[
  {"username": "user1"},
  {"username": "user2"},
  {"username": "user3", "avatar": "https://...", "background": "https://..."}
]

说明：
 - 允许为每个对象添加可选字段（例如 "avatar" 或 "background"），但必须包含 "username"。
 - 文件应使用 UTF-8 编码。
EXAMPLE
        exit 1
    fi

    # 复制到目标文件名
    cp "$EXTERNAL_JSON" "$KOL_LIST_FILE"
    echo "✅ 已复制 $EXTERNAL_JSON 到 $KOL_LIST_FILE"

else
    # 默认为从数据库创建
    echo "📖 选择从数据库创建 KOL 列表（使用 $KOL_DB_FILE 和 create_kol_list.py）"

    # 检查数据库文件是否存在
    if [[ ! -f "$KOL_DB_FILE" ]]; then
        echo "❌ 数据库文件不存在: $KOL_DB_FILE"
        echo "请确保数据库文件存在，或者修改脚本中的 KOL_DB_FILE 变量"
        exit 1
    fi

    # 检查Python脚本是否存在
    if [[ ! -f "create_kol_list.py" ]]; then
        echo "❌ Python脚本不存在: create_kol_list.py"
        echo "请确保 create_kol_list.py 文件在当前目录"
        exit 1
    fi

    # 调用Python脚本从数据库读取KOL列表
    echo "📖 正在从 $KOL_DB_FILE 读取KOL用户名..."

    # 构建命令参数
    CREATE_KOL_CMD="python3 create_kol_list.py --db \"$KOL_DB_FILE\" --output \"$KOL_LIST_FILE\""

    # 如果设置了最大KOL数量限制，添加--limit参数
    if [[ $MAX_KOL_COUNT -gt 0 ]]; then
        CREATE_KOL_CMD="$CREATE_KOL_CMD --limit $MAX_KOL_COUNT"
        echo "🔢 限制读取最多 $MAX_KOL_COUNT 个KOL用户"
    else
        echo "📊 读取数据库中的所有KOL用户"
    fi

    # 执行命令
    if eval $CREATE_KOL_CMD; then
        echo "✅ 成功创建 $KOL_LIST_FILE"
    else
        echo "❌ 创建KOL列表失败"
        exit 1
    fi
fi

# 检查生成的JSON文件
if [[ ! -f "$KOL_LIST_FILE" ]]; then
    echo "❌ KOL列表文件创建失败: $KOL_LIST_FILE"
    exit 1
fi

# 显示KOL数量
kol_count=$(python3 -c "import json; data=json.load(open('$KOL_LIST_FILE')); print(len(data))")
echo "📊 共读取到 $kol_count 个KOL账户"

# ╭──────────────── 获取用户信息 ─────────────╮
echo -e "\n[Step 2] 获取KOL用户信息 ..."
if python3 GetSeedKOL.py --input "$KOL_LIST_FILE"; then
    echo "✅ 用户信息获取完成"
else
    echo "⚠️  用户信息获取可能出现问题，但继续执行..."
fi

# ╭──────────────── 从followingA.db更新kol_list.json ─────────────╮
echo -e "\n[Step 3] 从followingA.db更新KOL列表 (包含头像和背景图片URL) ..."
if [[ -f "followingA.db" ]]; then
    # 备份原始kol_list.json
    if [[ -f "$KOL_LIST_FILE" ]]; then
        backup_file="${KOL_LIST_FILE}.bak"
        mv "$KOL_LIST_FILE" "$backup_file"
        echo "📑 已备份原始KOL列表到 $backup_file"
    fi
    
    # 创建临时Python脚本来从followingA.db导出数据
    cat > export_kol_list.py << 'EOF'
#!/usr/bin/env python3
import sqlite3
import json
import os

def export_kol_list_from_db(db_path="followingA.db", output_file="kol_list.json"):
    try:
        # 连接到数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有用户信息
        cursor.execute('''
            SELECT username, avatar_url, banner_url FROM users
        ''')
        
        users = []
        for row in cursor.fetchall():
            username, avatar_url, banner_url = row
            user_data = {
                "username": username,
                "avatar": avatar_url if avatar_url else "",
                "background": banner_url if banner_url else ""
            }
            users.append(user_data)
        
        # 关闭数据库连接
        conn.close()
        
        # 写入JSON文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 成功从 {db_path} 导出 {len(users)} 个KOL信息到 {output_file}")
        return len(users)
        
    except Exception as e:
        print(f"❌ 导出KOL列表时出错: {str(e)}")
        return 0

if __name__ == "__main__":
    export_kol_list_from_db()
EOF
    
    # 执行导出脚本
    chmod +x export_kol_list.py
    if python3 export_kol_list.py; then
        # 更新KOL数量
        kol_count=$(python3 -c "import json; data=json.load(open('$KOL_LIST_FILE')); print(len(data))")
        echo "📊 已更新KOL列表，共包含 $kol_count 个KOL账户"
        
        # 删除临时脚本
        rm export_kol_list.py
    else
        echo "⚠️ 从followingA.db更新KOL列表失败，将继续使用原始列表"
        # 如果导出失败，恢复备份
        if [[ -f "$backup_file" ]]; then
            mv "$backup_file" "$KOL_LIST_FILE"
        fi
    fi
else
    echo "⚠️ followingA.db不存在，将继续使用原始KOL列表"
fi

# # ╭──────────────── 抓取KOL推文 ──────────────╮
# echo -e "\n[Step 4] 抓取指定KOL的推文 (每个KOL最多${MAX_TWEETS}条推文) ..."
# if python3 KOLTweetCrawler.py --db_dir . --max_tweets $MAX_TWEETS --max_concurrent_tasks $MAX_CONCURRENT_TASKS; then
#     echo "✅ 推文抓取完成"
# else
#     echo "❌ 推文抓取失败"
#     exit 1
# fi


# ╭──────────────── 抓取KOL推文 ──────────────╮
echo -e "\n[Step 4] 抓取指定KOL的推文 (每个KOL最多${MAX_TWEETS}条推文) ..."

# 询问用户是否要抓取评论
echo -n "是否要抓取推文的评论？这会增加抓取时间和API调用次数 [y/N]: "
read -r response
case "$response" in
    [yY][eE][sS]|[yY])
        echo "✅ 将抓取推文和评论"
        SKIP_COMMENTS_FLAG=""
        ;;
    *)
        echo "⚠️ 将跳过评论抓取，仅抓取推文"
        SKIP_COMMENTS_FLAG="--skip_comments"
        ;;
esac

if python3 KOLTweetCrawler.py --db_dir . --max_tweets $MAX_TWEETS --max_concurrent_tasks $MAX_CONCURRENT_TASKS $SKIP_COMMENTS_FLAG; then
    echo "✅ 推文抓取完成"
else
    echo "❌ 推文抓取失败"
    exit 1
fi



# ╭──────────────── 识别交易建议 ──────────────╮
echo -e "\n[Step 5] 从推文中识别交易建议..."
if [[ ! -f "generate_trade_tweets.py" ]]; then
    echo "❌ generate_trade_tweets.py 文件不存在"
    echo "请确保 generate_trade_tweets.py 文件在当前目录"
    exit 1
fi

echo "🤖 使用AI分析推文内容，识别加密货币交易建议..."
if python3 generate_trade_tweets.py --db_dir . --api_key "$OPENAI_API_KEY" --max_concurrent 10 --blacklist "crypto_blacklist.txt"; then
    echo "✅ 交易建议识别完成"
else
    echo "❌ 交易建议识别失败"
    exit 1
fi

# 检查生成的数据库
if [[ ! -f "guid_to_trade_tweet.db" ]]; then
    echo "❌ guid_to_trade_tweet.db 生成失败"
    exit 1
fi

# 显示交易建议统计
trade_advice_count=$(python3 -c "
import sqlite3
conn = sqlite3.connect('guid_to_trade_tweet.db')
cursor = conn.cursor()
count = cursor.execute('SELECT COUNT(*) FROM trade_tweets WHERE has_trade_advice = 1').fetchone()[0]
conn.close()
print(count)
")
echo "📊 识别到 $trade_advice_count 条包含交易建议的记录"

# ╭──────────────── 分析加密货币趋势 ──────────────╮
echo -e "\n[Step 6] 分析加密货币趋势..."
if [[ ! -f "analyze_crypto_trends_concurrent.py" ]]; then
    echo "❌ analyze_crypto_trends_concurrent.py 文件不存在"
    echo "请确保 analyze_crypto_trends_concurrent.py 文件在当前目录"
    exit 1
fi

echo "📈 分析加密货币投资期限和趋势..."
if python3 analyze_crypto_trends_concurrent.py --db_dir . --api_key "$OPENAI_API_KEY" --max_concurrent 10; then
    echo "✅ 加密货币趋势分析完成"
else
    echo "❌ 加密货币趋势分析失败"
    exit 1
fi

# 检查最终输出数据库
if [[ ! -f "crypto_recommendations.db" ]]; then
    echo "❌ crypto_recommendations.db 生成失败"
    exit 1
fi

# 显示最终统计
recommendation_count=$(python3 -c "
import sqlite3
conn = sqlite3.connect('crypto_recommendations.db')
cursor = conn.cursor()
count = cursor.execute('SELECT COUNT(*) FROM crypto_recommendations').fetchone()[0]
conn.close()
print(count)
")

# ╭──────────────── 完成 ─────────────────────╮
cat <<EOF

🎉 完整流程执行完成！生成文件：

📁 数据文件：
  • $KOL_LIST_FILE - 包含${kol_count}个KOL的用户名列表(含头像和背景URL)
  • followingA.db - 包含KOL的详细信息
  • tweets.db - 包含${kol_count}个KOL的最近${MAX_TWEETS}条推文及评论
  • guid_to_trade_tweet.db - 包含${trade_advice_count}条交易建议记录
  • crypto_recommendations.db - 包含${recommendation_count}条加密货币推荐分析

📈 处理统计：
  • 数据源: $KOL_DB_FILE
  • KOL数量: $kol_count$(if [[ $MAX_KOL_COUNT -gt 0 ]]; then echo " (限制: $MAX_KOL_COUNT)"; fi)
  • 每个KOL最大推文数: $MAX_TWEETS
  • 识别的交易建议: $trade_advice_count 条
  • 最终推荐记录: $recommendation_count 条

📊 数据流程：
  $KOL_DB_FILE → kol_list.json → followingA.db → tweets.db → guid_to_trade_tweet.db → crypto_recommendations.db

💡 提示：
  • 最终分析结果保存在 crypto_recommendations.db 中
  • 可以使用 SQLite 工具查看和分析数据
  • 如需重新运行某个步骤，请先删除对应的输出文件
EOF

# 可选：将最终输出拷贝到上一级目录的 data 文件夹（受环境变量控制）
if [[ "${COPY_OUTPUTS:-1}" == "1" ]]; then
    TARGET_DATA_DIR="$OUTPUT_DATA_DIR"
    echo -e "\n[Post] 将输出文件复制到 $TARGET_DATA_DIR ..."
    mkdir -p "$TARGET_DATA_DIR"

    if [[ -f "crypto_recommendations.db" ]]; then
        cp "crypto_recommendations.db" "$TARGET_DATA_DIR/"
        echo "✅ 已复制 crypto_recommendations.db 到 $TARGET_DATA_DIR/"
    else
        echo "⚠️ 找不到 crypto_recommendations.db，跳过复制。"
    fi

    if [[ -f "kol_list.json" ]]; then
        cp "kol_list.json" "$TARGET_DATA_DIR/"
        echo "✅ 已复制 kol_list.json 到 $TARGET_DATA_DIR/"
    else
        echo "⚠️ 找不到 kol_list.json，跳过复制。"
    fi
else
    echo -e "\n[Post] 跳过复制步骤（环境变量 COPY_OUTPUTS=${COPY_OUTPUTS} 指定）。要启用复制，请设置 COPY_OUTPUTS=1 或取消该环境变量。"
fi
