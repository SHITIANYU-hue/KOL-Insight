import dotenv
dotenv.load_dotenv()
import json
import os
import asyncio
from typing import Optional, Dict, Any
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 限制 GPT API 并发数的 Semaphore，默认最多 10 个并发请求
_gpt_semaphore = asyncio.Semaphore(10)

async def call_gpt(prompt: str, json_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    异步调用 GPT API
    
    Args:
        prompt: 提示词
        json_schema: 可选的 JSON 结构，如果提供，GPT 会按照该结构回复
    
    Returns:
        解析后的字典，如果有 json_schema 则返回符合该结构的字典
    """
    
    
    async with _gpt_semaphore:
        messages = [{"role": "user", "content": prompt}]
        
        if json_schema:
            messages.append({
                "role": "system",
                "content": f"请按照以下 JSON 结构回复，不要添加任何其他内容，保证结果可以直接被解析：\n{json.dumps(json_schema, ensure_ascii=False, indent=2)}"
            })
            response_format = {"type": "json_object"}
        else:
            response_format = None
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format=response_format
        )
        content = response.choices[0].message.content
        if json_schema:
            return json.loads(content)
        else:
            return content


if __name__ == "__main__":
    import asyncio
    response = asyncio.run(call_gpt("Hello, how are you?"))
    print(response)
    test_json = {
        "name": "一个中文名字",
        "age": "整数，年龄",
        "email": "电子邮件地址"
    }
    response = asyncio.run(call_gpt("帮我虚构一个角色，请按照给定的json结构回复", test_json))
    print(response)