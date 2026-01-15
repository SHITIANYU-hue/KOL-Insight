#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  start.sh — KOL Pipeline  · 2025-07  (推文+分析+GPT 评定)
# -----------------------------------------------------------------------------
#  新的文件夹结构版本
#  步骤
#   0)  GetSeedInfo.py           → data/input/twitter_users.json
#   P)  filter_processed_users.py → 过滤已处理用户
#   F)  u03_2_625.py 递归抓 following → data/temp/following*.db
#   M)  合并 following*.db        → data/output/followingA.db
#   T)  1.py   抓推文+评论        → data/output/tweets.db
#   A)  analyze_twitter_data.py  → data/output/analytics.db
#   K)  kol_pipeline.py          → data/output/KOL_yes.db / KOL_no.db
#   C)  kol_comments.py          → data/output/tweetsA.db
# -----------------------------------------------------------------------------
# 如果报错请先执行dos2unix start.sh
# 如果dos2unix command not found，请先安装dos2unix
set -euo pipefail

# ╭──────────────── 初始化环境 ────────────────╮
echo "🚀 KOL Pipeline 启动"
echo "📁 检查目录结构..."

# 获取脚本所在的绝对路径
WORKSPACE_DIR=$(pwd)
echo "🏠 工作目录: $WORKSPACE_DIR"

# 确保必要的目录存在
mkdir -p data/input data/output data/temp logs config

# 检查Python脚本是否存在
SCRIPTS_DIR="scripts"
REQUIRED_SCRIPTS=("GetSeedInfo.py" "u03_2_625.py" "1.py" "analyze_twitter_data.py" "kol_pipeline.py" "kol_comments.py" "utils/filter_processed_users.py")

# 修改检测逻辑，在scripts及其子文件夹中查找脚本
for script in "${REQUIRED_SCRIPTS[@]}"; do
    FOUND=false
    # 在scripts目录及其所有子目录中查找脚本
    if find "$SCRIPTS_DIR" -name "$(basename "$script")" -type f -print -quit | grep -q .; then
        FOUND=true
    fi
    
    if [[ "$FOUND" == "false" ]]; then
        echo "❌ 缺少必需脚本: $script (在scripts及其子文件夹中未找到)"
        exit 1
    fi
done

# ╭──────────────── 种子用户选择 ────────────────╮
# 检查是否有现有的KOL结果可作为种子
if [[ -f "data/output/KOL_yes.db" ]]; then
    echo -e "\n🔍 检测到已有KOL_yes.db文件，可以将其中的用户作为新的种子。"
    read -rp "是否使用KOL_yes.db中的用户作为种子？(y/n，默认 n)：" USE_KOL_AS_SEED
    USE_KOL_AS_SEED=${USE_KOL_AS_SEED:-n}
    
    if [[ $USE_KOL_AS_SEED =~ ^[Yy]$ ]]; then
        echo "📊 从KOL_yes.db提取用户信息..."
        
        # 备份现有的author.json（如果存在）
        if [[ -f "data/input/author.json" ]]; then
            BACKUP_NAME="data/input/author.json.backup.$(date +%Y%m%d_%H%M%S)"
            mv data/input/author.json "$BACKUP_NAME"
            echo "📋 已备份现有种子文件到: $BACKUP_NAME"
        fi
        
        # 从KOL_yes.db提取用户名并创建新的author.json
        echo "[" > data/input/author.json
        sqlite3 data/output/KOL_yes.db "SELECT '  {\"username\": \"' || screen_name || '\"},' FROM users;" | \
            head -n -1 >> data/input/author.json
        # 添加最后一个用户（没有逗号）
        sqlite3 data/output/KOL_yes.db "SELECT '  {\"username\": \"' || screen_name || '\"}' FROM users ORDER BY rowid DESC LIMIT 1;" >> data/input/author.json
        echo "]" >> data/input/author.json
        
        SEED_COUNT=$(sqlite3 data/output/KOL_yes.db "SELECT COUNT(*) FROM users;")
        echo "✅ 已成功从KOL_yes.db创建新的种子文件，包含 $SEED_COUNT 个用户"
    else
        echo "📝 将使用现有的种子文件"
    fi
fi

# 检查输入文件
if [[ ! -f "data/input/author.json" ]]; then
    echo "❌ 缺少种子用户文件: data/input/author.json"
    echo "📝 请将您的种子用户文件放在 data/input/author.json"
    exit 1
fi

echo "✅ 目录结构和文件检查完成"

# ╭──────────────── 用户输入 ────────────────╮
read -rp "请设定你需要的 KOL 人数：" KOL_COUNT
[[ -z "$KOL_COUNT" || ! $KOL_COUNT =~ ^[0-9]+$ ]] && { echo "❌ 请输入整数"; exit 1; }
read -rp "请输入每个用户最多获取的推文数量 (默认 100)：" MAX_TWEETS
MAX_TWEETS=${MAX_TWEETS:-100}
read -rp "请输入following数量阈值 (默认 3500，超过此数量的用户将被跳过)：" FOLLOWING_THRESHOLD
FOLLOWING_THRESHOLD=${FOLLOWING_THRESHOLD:-3500}

# 新增：检查是否继续之前的爬取任务
CONTINUE_FROM_EXISTING=""
if [[ -f "data/output/followingA.db" ]]; then
    EXISTING_COUNT=$(sqlite3 data/output/followingA.db "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "0")
    if [[ $EXISTING_COUNT -gt 0 ]]; then
        echo -e "\n🔍 检测到已存在的 data/output/followingA.db，包含 $EXISTING_COUNT 个用户"
        read -rp "是否在现有数据基础上继续爬取？(y/n，默认 n)：" CONTINUE_CHOICE
        CONTINUE_CHOICE=${CONTINUE_CHOICE:-n}
        if [[ $CONTINUE_CHOICE =~ ^[Yy]$ ]]; then
            CONTINUE_FROM_EXISTING="data/output/followingA.db"
            echo "✅ 将排除 data/output/followingA.db 中已存在的 $EXISTING_COUNT 个用户"
        else
            echo "📝 将从头开始，现有数据将被备份"
        fi
    fi
fi

MAX_THRESHOLD=$(( KOL_COUNT * 10 ))
printf '\nMax_Threshold 设置为 %d (KOL ×10)\n' "$MAX_THRESHOLD"
printf 'Following_Threshold 设置为 %d\n' "$FOLLOWING_THRESHOLD"

# ╭──────────────── Step‑0 解析种子 ─────────╮
echo -e "\n[Step 0] 解析种子用户 …"
echo "📊 输入: data/input/author.json → 输出: data/input/twitter_users.json"

# 查找GetSeedInfo.py的实际位置
GETSEEDINFO_SCRIPT=$(find scripts -name "GetSeedInfo.py" -type f | head -n 1)
if [[ -z "$GETSEEDINFO_SCRIPT" ]]; then
    echo "❌ 无法找到 GetSeedInfo.py 脚本"
    exit 1
fi

# 切换到脚本所在目录
SCRIPT_DIR=$(dirname "$GETSEEDINFO_SCRIPT")

# 使用绝对路径
INPUT_PATH="$WORKSPACE_DIR/data/input/author.json"
OUTPUT_PATH="$WORKSPACE_DIR/data/input/twitter_users.json"

cd "$SCRIPT_DIR"
python3 $(basename "$GETSEEDINFO_SCRIPT") \
    --input "$INPUT_PATH" \
    --output "$OUTPUT_PATH" \
    --export_json
cd - > /dev/null

# 检查种子用户处理结果
if [[ ! -f "data/input/twitter_users.json" ]]; then
    echo "❌ 种子用户处理失败，未生成 twitter_users.json"
    exit 1
fi

SEED_COUNT=$(python3 -c "import json; print(len(json.load(open('data/input/twitter_users.json'))))" 2>/dev/null || echo "0")
echo "✅ 种子用户处理完成，共 $SEED_COUNT 个用户"

# ╭──────────────── Step‑P 过滤已处理用户 ─────╮
if [[ -f "data/output/followingA.db" ]]; then
    echo -e "\n[Step P] 过滤已处理过的用户 …"
    echo "📊 输入: data/input/twitter_users.json → 输出: data/input/twitter_users_filtered.json"
    
    # 查找filter_processed_users.py的实际位置
    FILTER_SCRIPT=$(find scripts -name "filter_processed_users.py" -type f | head -n 1)
    if [[ -z "$FILTER_SCRIPT" ]]; then
        echo "⚠️ 无法找到 filter_processed_users.py 脚本，将跳过过滤步骤"
    else
        # 备份原始文件
        cp "$OUTPUT_PATH" "${OUTPUT_PATH}.original"
        
        # 切换到脚本所在目录
        SCRIPT_DIR=$(dirname "$FILTER_SCRIPT")
        FILTERED_PATH="$WORKSPACE_DIR/data/input/twitter_users_filtered.json"
        DB_PATH="$WORKSPACE_DIR/data/output/followingA.db"
        
        cd "$SCRIPT_DIR"
        python3 $(basename "$FILTER_SCRIPT") \
            --input "$OUTPUT_PATH" \
            --output "$FILTERED_PATH" \
            --db "$DB_PATH"
        cd - > /dev/null
        
        # 如果过滤成功，替换原始文件
        if [[ -f "$FILTERED_PATH" ]]; then
            mv "$FILTERED_PATH" "$OUTPUT_PATH"
            FILTERED_COUNT=$(python3 -c "import json; print(len(json.load(open('$OUTPUT_PATH'))))" 2>/dev/null || echo "0")
            REMOVED_COUNT=$((SEED_COUNT - FILTERED_COUNT))
            echo "✅ 过滤完成，移除了 $REMOVED_COUNT 个已处理的用户，剩余 $FILTERED_COUNT 个用户"
        else
            echo "⚠️ 过滤过程失败，将使用原始用户列表"
        fi
    fi
else
    echo "ℹ️ 未发现现有的 followingA.db，跳过过滤步骤"
fi

# ╭──────────────── Step‑F 抓 following ─────╮
CYCLE=1; TOTAL_VALID=0

# 如果是继续模式，先统计现有用户数
if [[ -n "$CONTINUE_FROM_EXISTING" ]]; then
    TOTAL_VALID=$(sqlite3 "$CONTINUE_FROM_EXISTING" "SELECT COUNT(*) FROM users;")
    echo "📊 继续模式：当前已有 $TOTAL_VALID 个用户"
fi

while true; do
    # 设置输入输出路径
    if [[ $CYCLE -eq 1 ]]; then
        INP="$WORKSPACE_DIR/data/input/twitter_users.json"
    else
        INP="$WORKSPACE_DIR/data/temp/following$((CYCLE-1)).db"
    fi
    OUT="$WORKSPACE_DIR/data/temp/following${CYCLE}.db"
    
    printf "\n[Step F-%d] 输入：%s → 输出：%s" "$CYCLE" "$INP" "$OUT"
    
    # 构建排除参数
    EXCLUDE_PARAM=""
    if [[ -n "$CONTINUE_FROM_EXISTING" ]]; then
        EXCLUDE_PARAM="--exclude_db $WORKSPACE_DIR/$CONTINUE_FROM_EXISTING"
        printf " (排除：%s)" "$CONTINUE_FROM_EXISTING"
    elif [[ $CYCLE -gt 1 ]]; then
        # 如果不是继续模式，但是第2轮及以后，排除前面所有轮次的数据
        EXCLUDE_PARAM="--exclude_db $WORKSPACE_DIR/data/temp/following$((CYCLE-1)).db"
        printf " (排除：following%d.db)" "$((CYCLE-1))"
    fi
    printf "\n"

    # 查找u03_2_625.py的实际位置
    U03_SCRIPT=$(find scripts -name "u03_2_625.py" -type f | head -n 1)
    if [[ -z "$U03_SCRIPT" ]]; then
        echo "❌ 无法找到 u03_2_625.py 脚本"
        exit 1
    fi
    
    # 切换到脚本所在目录
    SCRIPT_DIR=$(dirname "$U03_SCRIPT")
    cd "$SCRIPT_DIR"
    
    # 执行爬取命令
    if [[ -n "$EXCLUDE_PARAM" ]]; then
        python3 $(basename "$U03_SCRIPT") --input "$INP" --output "$OUT" \
                           --cycle "$CYCLE" --max_threshold "$MAX_THRESHOLD" \
                           --following_threshold "$FOLLOWING_THRESHOLD" $EXCLUDE_PARAM
    else
        python3 $(basename "$U03_SCRIPT") --input "$INP" --output "$OUT" \
                           --cycle "$CYCLE" --max_threshold "$MAX_THRESHOLD" \
                           --following_threshold "$FOLLOWING_THRESHOLD"
    fi
    
    cd - > /dev/null

    # 统计新增用户
    ADDED=$(sqlite3 "data/temp/following${CYCLE}.db" "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "0")
    
    # 如果是继续模式，第一轮不累加到TOTAL_VALID（因为已经统计过了）
    if [[ -n "$CONTINUE_FROM_EXISTING" && $CYCLE -eq 1 ]]; then
        printf "第%d次循环完成，新增 %s 个有效用户 (总计已有 %s)\n" "$CYCLE" "$ADDED" "$TOTAL_VALID"
        # 重置继续标志，后续轮次正常累加
        CONTINUE_FROM_EXISTING=""
    else
        TOTAL_VALID=$(( TOTAL_VALID + ADDED ))
        printf "第%d次循环完成，新增 %s 个有效用户 (累计 %s)\n" "$CYCLE" "$ADDED" "$TOTAL_VALID"
    fi

    # 检查是否达到目标或无新增用户
    [[ $TOTAL_VALID -ge $MAX_THRESHOLD || $ADDED -eq 0 ]] && break
    CYCLE=$(( CYCLE + 1 ))
    
    # 避免无限循环
    [[ $CYCLE -gt 10 ]] && { echo "⚠️  达到最大循环次数(10)，停止爬取"; break; }
done

# ╭──────────────── Step‑M 合并 DB ──────────╮
echo -e "\n[Step Merge] 合并 data/temp/following*.db → data/output/followingA.db"

# 备份现有的followingA.db（如果存在）
if [[ -f "data/output/followingA.db" ]]; then
    BACKUP_NAME="data/output/followingA.db.backup.$(date +%Y%m%d_%H%M%S)"
    mv data/output/followingA.db "$BACKUP_NAME"
    echo "📋 已备份现有数据库到: $BACKUP_NAME"
fi

# 创建新的合并数据库
FIRST_DB="$WORKSPACE_DIR/data/temp/following1.db"
if [[ ! -f "$FIRST_DB" ]]; then
    echo "❌ 找不到 $FIRST_DB，无法合并"
    exit 1
fi

echo "🔧 创建合并数据库结构..."
sqlite3 data/output/followingA.db "ATTACH '$FIRST_DB' AS src; 
CREATE TABLE users AS SELECT * FROM src.users WHERE 0; 
CREATE TABLE following_relationships AS SELECT * FROM src.following_relationships WHERE 0; 
CREATE TABLE processing_status AS SELECT * FROM src.processing_status WHERE 0;
DETACH src;"

# 合并所有following*.db文件
for n in $(seq 1 "$CYCLE"); do
    DB="$WORKSPACE_DIR/data/temp/following${n}.db"
    if [[ -f "$DB" ]]; then
        echo "  · 合并 $DB"
        sqlite3 data/output/followingA.db "ATTACH '$DB' AS s; 
        INSERT OR IGNORE INTO users SELECT * FROM s.users; 
        INSERT OR IGNORE INTO following_relationships SELECT * FROM s.following_relationships; 
        INSERT OR IGNORE INTO processing_status SELECT * FROM s.processing_status;
        DETACH s;"
    else
        echo "  ⚠️  跳过不存在的文件: $DB"
    fi
done

# 统计合并结果
MERGED_USERS=$(sqlite3 data/output/followingA.db "SELECT COUNT(*) FROM users;")
MERGED_RELS=$(sqlite3 data/output/followingA.db "SELECT COUNT(*) FROM following_relationships;")
echo "✅ Merge 完成："
echo "   • 用户数: $MERGED_USERS"
echo "   • 关注关系: $MERGED_RELS"

# 显示数据质量统计
echo -e "\n📊 数据质量统计:"
VERIFIED_COUNT=$(sqlite3 data/output/followingA.db "SELECT COUNT(*) FROM users WHERE verified = 1;" 2>/dev/null || echo "0")
HIGH_FOLLOWERS=$(sqlite3 data/output/followingA.db "SELECT COUNT(*) FROM users WHERE followers_count > 100000;" 2>/dev/null || echo "0")
echo "   • 认证用户: $VERIFIED_COUNT"
echo "   • 高粉丝用户(>10万): $HIGH_FOLLOWERS"

# ╭──────────────── Step‑T 抓推文 ────────────╮
printf "\n[Step Tweets] 抓取推文 (max_tweets=%s, 并发=%s)\n" "$MAX_TWEETS" "20"

# 查找1.py的实际位置
TWEETS_SCRIPT=$(find scripts -name "1.py" -type f | head -n 1)
if [[ -z "$TWEETS_SCRIPT" ]]; then
    echo "❌ 无法找到 1.py 脚本"
    exit 1
fi

# 切换到脚本所在目录
SCRIPT_DIR=$(dirname "$TWEETS_SCRIPT")
cd "$SCRIPT_DIR"
python3 $(basename "$TWEETS_SCRIPT") --db_dir "$WORKSPACE_DIR/data/output" --max_tweets "$MAX_TWEETS" --max_concurrent_tasks 20
cd - > /dev/null

# ╭──────────────── Step‑A 指标分析 ─────────╮
echo -e "\n[Step Analytics] 计算互动/原创性指标"

# 查找analyze_twitter_data.py的实际位置
ANALYZE_SCRIPT=$(find scripts -name "analyze_twitter_data.py" -type f | head -n 1)
if [[ -z "$ANALYZE_SCRIPT" ]]; then
    echo "❌ 无法找到 analyze_twitter_data.py 脚本"
    exit 1
fi

# 切换到脚本所在目录
SCRIPT_DIR=$(dirname "$ANALYZE_SCRIPT")
cd "$SCRIPT_DIR"
python3 $(basename "$ANALYZE_SCRIPT") --db_dir "$WORKSPACE_DIR/data/output"
cd - > /dev/null

# ╭──────────────── Step‑K GPT KOL 筛选 ─────╮
printf "\n[Step KOL] GPT 评定 (目标 KOL=%s)\n" "$KOL_COUNT"

# 查找kol_pipeline.py的实际位置
KOL_SCRIPT=$(find scripts -name "kol_pipeline.py" -type f | head -n 1)
if [[ -z "$KOL_SCRIPT" ]]; then
    echo "❌ 无法找到 kol_pipeline.py 脚本"
    exit 1
fi

# 切换到脚本所在目录
SCRIPT_DIR=$(dirname "$KOL_SCRIPT")
cd "$SCRIPT_DIR"
python3 $(basename "$KOL_SCRIPT") --db_dir "$WORKSPACE_DIR/data/output" --target_kols "$KOL_COUNT" --max_tweets "$MAX_TWEETS"
cd - > /dev/null

# ╭──────────────── Step‑C KOL 评论爬取 ─────╮
printf "\n[Step Comments] 爬取 KOL 推文评论 (并发=5)\n"

# 查找kol_comments.py的实际位置
COMMENTS_SCRIPT=$(find scripts -name "kol_comments.py" -type f | head -n 1)
if [[ -z "$COMMENTS_SCRIPT" ]]; then
    echo "❌ 无法找到 kol_comments.py 脚本"
    exit 1
fi

# 切换到脚本所在目录
SCRIPT_DIR=$(dirname "$COMMENTS_SCRIPT")
cd "$SCRIPT_DIR"
python3 $(basename "$COMMENTS_SCRIPT") --db_dir "$WORKSPACE_DIR/data/output" --max_concurrent_tasks 5
cd - > /dev/null

# ╭──────────────── 完成 & 清理 ─────────────╮
echo -e "\n🧹 清理临时文件..."
# 可选：删除临时的following*.db文件，保留followingA.db
read -rp "是否删除临时的following1.db, following2.db等文件？(y/n，默认 n)：" CLEANUP_CHOICE
CLEANUP_CHOICE=${CLEANUP_CHOICE:-n}
if [[ $CLEANUP_CHOICE =~ ^[Yy]$ ]]; then
    for n in $(seq 1 "$CYCLE"); do
        DB="data/temp/following${n}.db"
        [[ -f "$DB" ]] && { rm "$DB"; echo "  🗑️  删除 $DB"; }
    done
    # 同时清理可能存在的 .shm 和 .wal 文件
    rm -f data/temp/following*.db-shm data/temp/following*.db-wal
    echo "✅ 临时文件清理完成"
fi

# ╭──────────────── 日志整理 ─────────────────╮
echo -e "\n📋 整理日志文件..."
# 移动可能散落的日志文件到logs目录
find . -maxdepth 2 -name "*.log" -not -path "./logs/*" -exec mv {} logs/ \; 2>/dev/null || true

# 创建流程完成时间戳
echo "Pipeline completed at: $(date)" > logs/pipeline_completion.log

# ╭──────────────── 结果展示 ─────────────────╮
cat <<EOF

🎉 全流程完成！生成文件：
  📊 数据文件：
    • data/output/followingA.db      (用户数据: $MERGED_USERS 个用户)
    • data/output/tweets.db          (推文数据)
    • data/output/analytics.db       (分析指标)
    • data/output/KOL_yes.db         (优质KOL: 目标 $KOL_COUNT 个)
    • data/output/KOL_no.db          (非KOL用户)
    • data/output/tweetsA.db         (含KOL评论)
  
  📁 目录结构：
    • data/input/     种子用户文件
    • data/output/    最终结果文件
    • data/temp/      临时处理文件
    • logs/           所有日志文件
  
  📈 数据统计：
    • 总爬取轮次: $CYCLE 轮
    • 认证用户: $VERIFIED_COUNT 个
    • 高粉丝用户: $HIGH_FOLLOWERS 个
    • 关注关系: $MERGED_RELS 条

📝 使用建议：
  1. 检查 logs/ 目录中的日志文件了解详细执行情况
  2. 使用 scripts/db_inspector.py 查看数据库内容
  3. 结果文件位于 data/output/ 目录中
  4. 下次运行时，将自动过滤掉已处理过的用户，提高效率

EOF