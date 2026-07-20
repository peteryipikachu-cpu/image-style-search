import base64
import requests
import os

# 配置
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
DOUBAO_MODEL_ID = "doubao-seed-2-0-lite-260215"

if not DOUBAO_API_KEY:
    print("缺少 DOUBAO_API_KEY，跳过豆包 API 测试。")
    raise SystemExit(0)

# 测试图片路径 - 找一个本地存在的图片
sample_image = None
data_dir = "/Users/pikachu/work/bodeng/yitusoutu/以图搜图_badcase"
for root, dirs, files in os.walk(data_dir):
    for file in files:
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            sample_image = os.path.join(root, file)
            break
    if sample_image:
        break

if not sample_image:
    print("未找到测试图片")
    exit(1)

print(f"使用测试图片: {sample_image}")

# 测试1: 先尝试用户示例中的方式
print("\n=== 测试1: 用户示例中的API端点格式...")
url1 = "https://ark.cn-beijing.volces.com/api/v3/responses"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {DOUBAO_API_KEY}"
}

# 尝试用示例图片URL的方式
payload1 = {
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
                    "text": "支持输入图片的模型系列是哪个？"
                }
            ]
        }
    ]
}

try:
    response = requests.post(url1, headers=headers, json=payload1, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text}")
except Exception as e:
    print(f"错误: {e}")
