#!/usr/bin/env python3
"""单独测试腾讯云图像搜索API"""

import os
import sys
import base64
import json
import requests
import hashlib
import hmac
import time
import random
from urllib.parse import urlencode, quote

# 禁用代理影响
os.environ['NO_PROXY'] = 'tencentcloudapi.com,.tencentcloudapi.com'
os.environ['no_proxy'] = 'tencentcloudapi.com,.tencentcloudapi.com'

SECRET_ID = os.getenv('TENCENT_SECRET_ID')
SECRET_KEY = os.getenv('TENCENT_SECRET_KEY')

if not SECRET_ID or not SECRET_KEY:
    print("缺少 TENCENT_SECRET_ID 或 TENCENT_SECRET_KEY，跳过腾讯云 API 测试。")
    sys.exit(0)

def test_basic_connectivity():
    """测试基础网络连通性"""
    print("=== 1. 测试基础网络连通性 ===")
    
    endpoints = [
        'https://image.tencentcloudapi.com',
        'https://imagesearch.tencentcloudapi.com',
        'https://image-search.tencentcloudapi.com'
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=10)
            print(f"✓ {endpoint} - 状态码: {response.status_code}")
        except Exception as e:
            print(f"✗ {endpoint} - 错误: {e}")

def test_api_endpoints():
    """测试不同的API端点"""
    print("\n=== 2. 测试不同API端点 ===")
    
    endpoints = [
        'image.tencentcloudapi.com',
        'imagesearch.tencentcloudapi.com',
        'image-search.tencentcloudapi.com',
        'cis.tencentcloudapi.com'
    ]
    
    versions = ['2020-12-15', '2021-05-19', '2022-01-01', '2023-01-01']
    
    return endpoints, versions

def generate_signature(params, secret_key, endpoint, method='GET'):
    """生成腾讯云API签名"""
    sorted_params = sorted(params.items())
    sign_str = '&'.join([f'{k}={quote(str(v), safe="-_.")}' for k, v in sorted_params])
    sign_str = f'{method}{endpoint}/?{sign_str}'
    
    print(f"签名字符串: {sign_str[:200]}...")
    
    signature = hmac.new(
        secret_key.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    return base64.b64encode(signature).decode('utf-8')

def test_various_combinations():
    """测试各种参数组合"""
    print("\n=== 3. 测试参数组合 ===")
    
    endpoints = [
        'image.tencentcloudapi.com',
        'imagesearch.tencentcloudapi.com'
    ]
    
    versions = ['2020-12-15', '2021-05-19']
    regions = ['ap-shanghai', 'ap-guangzhou', 'ap-beijing']
    actions = ['SearchImage', 'SearchImages', 'SearchImageByImage', 'Search']
    
    results = []
    
    for endpoint in endpoints:
        for version in versions:
            for region in regions:
                for action in actions:
                    print(f"\n测试: {endpoint}/{version}/{action}/{region}")
                    
                    params = {
                        'SecretId': SECRET_ID,
                        'Timestamp': int(time.time()),
                        'Nonce': random.randint(1, 65535),
                        'SignatureMethod': 'HmacSHA256',
                        'Action': action,
                        'Version': version,
                        'Region': region
                    }
                    
                    signature = generate_signature(params, SECRET_KEY, endpoint, method='POST')
                    params['Signature'] = signature
                    
                    url = f'https://{endpoint}/?{urlencode(params)}'
                    
                    # 只发送简单请求测试验证
                    payload = {'Limit': 1}
                    
                    try:
                        response = requests.post(url, json=payload, timeout=15)
                        result = response.json()
                        
                        if 'Response' in result:
                            if 'Error' in result['Response']:
                                print(f"  错误: {result['Response']['Error']}")
                                results.append((endpoint, version, action, region, 'ERROR', result['Response']['Error']))
                            else:
                                print(f"  ✓ 成功: {result}")
                                results.append((endpoint, version, action, region, 'SUCCESS', result))
                        else:
                            print(f"  响应异常: {result}")
                    except Exception as e:
                        print(f"  请求失败: {e}")
    
    return results

def main():
    print("="*60)
    print("腾讯云图像搜索API - 完整测试")
    print("="*60)
    
    test_basic_connectivity()
    endpoints, versions = test_api_endpoints()
    results = test_various_combinations()
    
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for r in results:
        print(f"{r[0]}/{r[1]}/{r[2]}/{r[3]}: {r[4]}")
        if len(r) > 5:
            print(f"  详情: {r[5]}")

if __name__ == '__main__':
    main()
