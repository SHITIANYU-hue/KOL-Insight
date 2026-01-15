# API密钥设置指南

## 概述

项目需要两个API密钥：

- **OPENAI_API_KEY** - 用于AI分析交易建议和查找CoinGecko ID
- **TWEETSCOUT_API_KEY** - 用于抓取Twitter用户信息和推文

## 获取API密钥

### OpenAI API密钥

1. 访问 [OpenAI API Platform](https://platform.openai.com/api-keys)
2. 登录或注册账户
3. 点击 "Create new secret key"
4. 复制生成的密钥（格式：`sk-proj-...` 或 `sk-...`）

### TweetScout API密钥

1. 访问 [TweetScout.io](https://tweetscout.io/)
2. 注册账户并选择合适的订阅计划
3. 在API设置中获取密钥（格式：`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`）

## 设置方法

### 方法1：环境变量（推荐）

#### Linux/MacOS

```bash
# 临时设置（当前终端会话有效）
export OPENAI_API_KEY='sk-proj-your-openai-key-here'
export TWEETSCOUT_API_KEY='your-tweetscout-key-here'

# 永久设置 - 添加到 ~/.bashrc 或 ~/.zshrc
echo 'export OPENAI_API_KEY="sk-proj-your-openai-key-here"' >> ~/.bashrc
echo 'export TWEETSCOUT_API_KEY="your-tweetscout-key-here"' >> ~/.bashrc
source ~/.bashrc

# 验证设置
echo $OPENAI_API_KEY
echo $TWEETSCOUT_API_KEY
```

#### Windows (CMD)

```cmd
REM 临时设置
set OPENAI_API_KEY=sk-proj-your-openai-key-here
set TWEETSCOUT_API_KEY=your-tweetscout-key-here

REM 永久设置
setx OPENAI_API_KEY "sk-proj-your-openai-key-here"
setx TWEETSCOUT_API_KEY "your-tweetscout-key-here"

REM 验证设置
echo %OPENAI_API_KEY%
echo %TWEETSCOUT_API_KEY%
```

#### Windows (PowerShell)

```powershell
# 临时设置
$env:OPENAI_API_KEY = "sk-proj-your-openai-key-here"
$env:TWEETSCOUT_API_KEY = "your-tweetscout-key-here"

# 永久设置
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-proj-your-openai-key-here", "User")
[Environment]::SetEnvironmentVariable("TWEETSCOUT_API_KEY", "your-tweetscout-key-here", "User")

# 验证设置
echo $env:OPENAI_API_KEY
echo $env:TWEETSCOUT_API_KEY
```

### 方法2：.env文件

创建项目根目录下的 `.env` 文件：

```env
# .env 文件
OPENAI_API_KEY=sk-proj-your-openai-key-here
TWEETSCOUT_API_KEY=your-tweetscout-key-here
```

然后在Python脚本中使用 `python-dotenv`：

```python
from dotenv import load_dotenv
import os

# 加载.env文件
load_dotenv()

# 获取API密钥
openai_key = os.getenv('OPENAI_API_KEY')
tweetscout_key = os.getenv('TWEETSCOUT_API_KEY')
```

安装依赖：

```bash
pip install python-dotenv
```

### 方法3：直接修改脚本（不推荐）

#### 修改start.sh

```bash
# 在start.sh开头直接设置
OPENAI_API_KEY="sk-proj-your-openai-key-here"
TWEETSCOUT_API_KEY="your-tweetscout-key-here"
```

#### 修改Python脚本

```python
# 在脚本开头直接设置
api_key = "sk-proj-your-openai-key-here"  # OpenAI密钥
tweetscout_key = "your-tweetscout-key-here"  # TweetScout密钥
```

### 方法4：命令行参数

直接在运行时指定：

```bash
# 运行单个脚本
python3 generate_trade_tweets.py --api_key "sk-proj-your-key-here"

# 运行完整流程时临时设置
OPENAI_API_KEY="sk-proj-your-key-here" ./start.sh
```

### 方法5：配置文件

创建 `config.json`：

```json
{
  "openai_api_key": "sk-proj-your-openai-key-here",
  "tweetscout_api_key": "your-tweetscout-key-here",
  "max_concurrent": 10,
  "max_tweets": 100
}
```

在Python中读取：

```python
import json

with open('config.json', 'r') as f:
    config = json.load(f)
    
openai_key = config['openai_api_key']
tweetscout_key = config['tweetscout_api_key']
```

## 当前代码中的使用情况

### GetSeedKOL.py

```python
# 硬编码在代码中（需要修改）
crawler = GetSeedKOL(
    api_key="tweetscout api",  # 当前的TweetScout密钥
    input_file=args.input
)
```

**建议修改为**：

```python
# 从环境变量获取
api_key = os.getenv("TWEETSCOUT_API_KEY", "tweetscout api")
crawler = GetSeedKOL(api_key=api_key, input_file=args.input)
```

### KOLTweetCrawler.py

```python
# 从环境变量读取，有默认值
api_key = os.getenv("TWEETSCOUT_API_KEY", args.api_key)
```

### start.sh

```bash
# 检查环境变量
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
if [[ -z "$OPENAI_API_KEY" ]]; then
    echo "❌ 请设置 OPENAI_API_KEY 环境变量"
    exit 1
fi
```

## 安全建议

### ✅ 推荐做法

1. **使用环境变量** - 最安全的方法
2. **使用.env文件** - 便于开发，记得添加到`.gitignore`
3. **权限控制** - 确保只有必要的用户能访问
4. **定期轮换** - 定期更新API密钥

### ❌ 避免做法

1. **硬编码在代码中** - 容易泄露
2. **提交到版本控制** - Git历史中永久保存
3. **明文存储** - 避免在日志中打印
4. **共享密钥** - 每个环境使用独立密钥

## 验证设置

### 检查环境变量

```bash
# Linux/MacOS
printenv | grep API_KEY

# Windows CMD  
set | findstr API_KEY

# Windows PowerShell
Get-ChildItem Env: | Where-Object {$_.Name -like "*API_KEY*"}
```

### 测试API连接

```python
# 测试OpenAI API
import openai
import os

client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
try:
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5
    )
    print("✅ OpenAI API连接成功")
except Exception as e:
    print(f"❌ OpenAI API连接失败: {e}")

# 测试TweetScout API  
import requests

headers = {"ApiKey": os.getenv('TWEETSCOUT_API_KEY')}
try:
    response = requests.get("https://api.tweetscout.io/v2/info/elonmusk", headers=headers)
    if response.status_code == 200:
        print("✅ TweetScout API连接成功")
    else:
        print(f"❌ TweetScout API连接失败: {response.status_code}")
except Exception as e:
    print(f"❌ TweetScout API连接失败: {e}")
```

## 快速设置脚本

创建 `setup_env.sh`：

```bash
#!/bin/bash
echo "🔑 API密钥设置向导"
echo ""

read -p "请输入OpenAI API密钥: " openai_key
read -p "请输入TweetScout API密钥: " tweetscout_key

echo ""
echo "export OPENAI_API_KEY='$openai_key'" >> ~/.bashrc
echo "export TWEETSCOUT_API_KEY='$tweetscout_key'" >> ~/.bashrc

echo "✅ API密钥已添加到 ~/.bashrc"
echo "🔄 请运行: source ~/.bashrc 或重新打开终端"
```

运行设置：

```bash
chmod +x setup_env.sh
./setup_env.sh
```

## 故障排除

### 常见错误

1. **401 Unauthorized**
	- 检查API密钥是否正确
	- 确认密钥未过期
	- 验证账户余额（OpenAI）
2. **环境变量未生效**
	- 重新启动终端
	- 检查拼写错误
	- 确认使用正确的shell配置文件
3. **权限错误**
	- 检查文件权限
	- 确认用户有权限访问环境变量
4. **网络连接问题**
	- 检查防火墙设置
	- 确认网络代理配置
	- 验证API服务状态

记住：永远不要将API密钥提交到版本控制系统中！