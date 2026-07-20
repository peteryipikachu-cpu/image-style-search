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

# 测试图片路径
data_dir = "/Users/pikachu/work/bodeng/yitusoutu/以图搜图_badcase"
test_images = []

for root, dirs, files in os.walk(data_dir):
    for file in files:
        if '结果图' in file and file.lower().endswith(('.jpg', '.jpeg', '.png')):
            test_images.append(os.path.join(root, file))
            if len(test_images) >= 3:  # 测试3张结果图
                break
    if len(test_images) >= 3:
        break

print("=== 豆包多模态分析 - 图片描述效果测试 ===\n")

for idx, image_path in enumerate(test_images):
    print(f"--- 图片 {idx+1}: {os.path.basename(image_path)} ---")
    
    # 读取图片并转换为base64
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    
    # 调用豆包API
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
                        "image_url": f"data:image/jpeg;base64,{base64_image}"
                    },
                    {
                        "type": "input_text",
                        "text": "请用英文简短描述这张图片的内容，包括主要对象、场景、颜色等，不超过30个词"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            caption = ""
            
            if "output" in result:
                for output_item in result["output"]:
                    if output_item.get("type") == "message":
                        for content_item in output_item.get("content", []):
                            if content_item.get("type") == "output_text":
                                caption = content_item.get("text", "").strip()
                                break
            
            if caption:
                print(f"📝 生成的描述: {caption}")
            else:
                print("❌ 未生成描述")
        else:
            print(f"❌ API调用失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 调用错误: {e}")
    
    print()
