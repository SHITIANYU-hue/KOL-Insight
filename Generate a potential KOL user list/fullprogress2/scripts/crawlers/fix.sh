#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  fix_python_syntax.sh — Python语法错误检查和修复工具
# -----------------------------------------------------------------------------

echo "🔧 Python语法错误诊断工具"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 设置路径
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
GET_SEED_SCRIPT="$SCRIPTS_DIR/crawlers/GetSeedInfo.py"

echo "检查的脚本: $GET_SEED_SCRIPT"
echo ""

# 1. 详细的语法检查
echo "1️⃣ 详细语法检查..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if python3 -m py_compile "$GET_SEED_SCRIPT" 2>&1; then
    echo "✅ 语法检查通过"
else
    echo "❌ 发现语法错误，详细信息如上"
fi

echo ""
echo "2️⃣ 文件编码检查..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v file &> /dev/null; then
    file "$GET_SEED_SCRIPT"
else
    echo "file命令不可用，跳过编码检查"
fi

echo ""
echo "3️⃣ 文件前几行检查..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "显示文件的前10行，检查是否有明显问题:"
head -n 10 "$GET_SEED_SCRIPT" | cat -n

echo ""
echo "4️⃣ 检查文件是否有Windows换行符..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v dos2unix &> /dev/null; then
    echo "检查并转换换行符..."
    dos2unix "$GET_SEED_SCRIPT"
    echo "✅ 换行符转换完成"
else
    echo "dos2unix不可用，手动检查换行符"
    if [[ -f "$GET_SEED_SCRIPT" ]]; then
        # 使用hexdump检查是否有\r\n
        if hexdump -C "$GET_SEED_SCRIPT" | head -n 5 | grep -q "0d 0a"; then
            echo "⚠️  检测到Windows换行符(CRLF)，这可能导致语法错误"
            echo "建议安装dos2unix或手动转换文件格式"
        else
            echo "✅ 换行符看起来正常"
        fi
    fi
fi

echo ""
echo "5️⃣ 重新测试语法..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if python3 -m py_compile "$GET_SEED_SCRIPT"; then
    echo "✅ 语法检查现在通过了！"
    
    echo ""
    echo "6️⃣ 测试help命令..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if timeout 10 python3 "$GET_SEED_SCRIPT" --help; then
        echo "✅ help命令成功"
    else
        echo "❌ help命令失败，可能缺少依赖包"
        echo ""
        echo "尝试安装依赖包..."
        
        # 检查requirements.txt
        if [[ -f "config/requirements.txt" ]]; then
            echo "找到 config/requirements.txt，安装依赖..."
            pip3 install -r config/requirements.txt
        elif [[ -f "requirements.txt" ]]; then
            echo "找到 requirements.txt，安装依赖..."
            pip3 install -r requirements.txt
        else
            echo "未找到requirements.txt，尝试安装常用包..."
            pip3 install requests sqlite3 json argparse
        fi
        
        echo ""
        echo "重新测试help命令..."
        if timeout 10 python3 "$GET_SEED_SCRIPT" --help; then
            echo "✅ 安装依赖后help命令成功"
        else
            echo "❌ 仍然失败，需要进一步检查"
        fi
    fi
else
    echo "❌ 语法检查仍然失败"
    echo ""
    echo "📋 可能的解决方案:"
    echo "1. 文件可能在移动过程中损坏"
    echo "2. 可能有不可见字符"
    echo "3. 可能需要重新复制文件"
    echo ""
    echo "🔧 手动修复建议:"
    echo "1. 检查原始文件是否正常"
    echo "2. 重新复制GetSeedInfo.py到scripts/crawlers/"
    echo "3. 确保文件使用UTF-8编码和LF换行符"
fi

echo ""
echo "7️⃣ 检查其他Python脚本..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
other_scripts=(
    "$SCRIPTS_DIR/crawlers/u03_2_625.py"
    "$SCRIPTS_DIR/crawlers/1.py"
    "$SCRIPTS_DIR/analysis/analyze_twitter_data.py"
    "$SCRIPTS_DIR/analysis/kol_pipeline.py"
    "$SCRIPTS_DIR/crawlers/kol_comments.py"
)

for script in "${other_scripts[@]}"; do
    if [[ -f "$script" ]]; then
        echo -n "检查 $(basename "$script"): "
        if python3 -m py_compile "$script" 2>/dev/null; then
            echo "✅ 语法正常"
        else
            echo "❌ 语法错误"
        fi
    else
        echo "❌ $(basename "$script") 不存在"
    fi
done

echo ""
echo "🎯 总结和建议:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "如果GetSeedInfo.py的语法问题已修复，请重新运行start_fixed.sh"
echo "如果仍有问题，可能需要检查原始文件或重新复制脚本文件"