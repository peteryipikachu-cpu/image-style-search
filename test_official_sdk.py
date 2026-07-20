#!/usr/bin/env python3
import os
import json
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.wimgs.v20251106 import wimgs_client, models

# 禁用代理
os.environ['NO_PROXY'] = 'tencentcloudapi.com,.tencentcloudapi.com'
os.environ['no_proxy'] = 'tencentcloudapi.com,.tencentcloudapi.com'

SECRET_ID = os.getenv('TENCENT_SECRET_ID')
SECRET_KEY = os.getenv('TENCENT_SECRET_KEY')

if not SECRET_ID or not SECRET_KEY:
    print("缺少 TENCENT_SECRET_ID 或 TENCENT_SECRET_KEY，跳过腾讯云 SDK 测试。")
    raise SystemExit(0)

def test_search_by_text():
    print("="*60)
    print("使用腾讯云官方SDK测试联网图像搜索")
    print("="*60)
    
    try:
        # 实例化一个认证对象
        cred = credential.Credential(SECRET_ID, SECRET_KEY)
        
        # 实例化一个http选项
        httpProfile = HttpProfile()
        httpProfile.endpoint = "wimgs.tencentcloudapi.com"
        
        # 实例化一个client选项
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        
        # 实例化要请求产品的client对象
        client = wimgs_client.WimgsClient(cred, "ap-guangzhou", clientProfile)
        
        # 实例化一个请求对象
        req = models.SearchByTextRequest()
        params = {
            "Query": "北京故宫"
        }
        req.from_json_string(json.dumps(params))
        
        print(f"\n发送请求: SearchByText, Text='北京故宫'")
        print("-"*60)
        
        # 返回的resp是一个SearchByTextResponse的实例
        resp = client.SearchByText(req)
        
        # 输出json格式的字符串回包
        print(f"响应成功!")
        print(resp.to_json_string())
        
        # 解析结果
        result_json = json.loads(resp.to_json_string())
        if 'Images' in result_json:
            images = result_json['Images']
            print(f"\n找到 {len(images)} 张图片:")
            for i, img_str in enumerate(images[:3]):  # 只显示前3张
                try:
                    img = json.loads(img_str)
                    print(f"\n图片 {i+1}:")
                    print(f"  标题: {img.get('title', '')}")
                    print(f"  缩略图: {img.get('thumbnailUrl', '')}")
                    print(f"  原图: {img.get('origPicUrl', '')}")
                except Exception as e:
                    print(f"\n图片 {i+1}: 解析失败 - {e}")
        
    except Exception as e:
        print(f"\n错误发生: {e}")

if __name__ == "__main__":
    test_search_by_text()
