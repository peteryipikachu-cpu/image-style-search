import base64
import requests
import os
import json

# 配置
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
DOUBAO_MODEL_ID = "doubao-seed-2-0-lite-260428"

if not DOUBAO_API_KEY:
    print("缺少 DOUBAO_API_KEY，跳过豆包 API 测试。")
    raise SystemExit(0)

# 测试豆包API - 使用公共图片URL
print("\n=== 测试豆包API ===")
url = "https://ark.cn-beijing.volces.com/api/v3/responses"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {DOUBAO_API_KEY}"
}

payload = {
    "model": DOUBAO_MODEL_ID,
    "input": [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/ark_demo_img_1.png"
                },
                {
                    "type": "input_text",
                    "text": "你看见了什么？"
                }
            ]
        }
    ]
}

try:
    print(f"正在调用豆包API...")
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text}")
    
    if response.status_code == 200:
        result = response.json()
        print("\n=== 解析响应 ===")
        print(f"完整响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
