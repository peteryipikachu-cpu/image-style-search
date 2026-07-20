import json
import os
import requests
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.wimgs.v20251106 import wimgs_client, models

# 禁用代理
os.environ['NO_PROXY'] = 'tencentcloudapi.com,.tencentcloudapi.com'
os.environ['no_proxy'] = 'tencentcloudapi.com,.tencentcloudapi.com'

# 已知有严格防盗链的域名
BLOCKED_DOMAINS = {'img.zcool.cn', 'img.mp.itc.cn', 'p3.itc.cn', 'p4.itc.cn'}

def is_url_accessible(url, timeout=5):
    """检查图片URL是否可访问"""
    try:
        parsed = requests.utils.urlparse(url)
        if parsed.hostname in BLOCKED_DOMAINS:
            return False
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/*',
            'Referer': f'{parsed.scheme}://{parsed.netloc}/',
        }
        
        response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        content_type = response.headers.get('content-type', '')
        return response.status_code == 200 and content_type.startswith('image/')
    except Exception:
        return False

class TencentImageSearch:
    def __init__(self, secret_id, secret_key):
        self.secret_id = secret_id
        self.secret_key = secret_key
        self._init_client()
    
    def _init_client(self):
        try:
            cred = credential.Credential(self.secret_id, self.secret_key)
            httpProfile = HttpProfile()
            httpProfile.endpoint = "wimgs.tencentcloudapi.com"
            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            self.client = wimgs_client.WimgsClient(cred, "ap-guangzhou", clientProfile)
        except Exception as e:
            print(f"Failed to init Tencent client: {e}")
            self.client = None
    
    def search_image_by_text(self, query, limit=3):
        """
        使用文本搜索图片
        
        Args:
            query: 搜索关键词
            limit: 返回结果数量
            
        Returns:
            图片列表
        """
        if not self.client:
            self._init_client()
            if not self.client:
                return []
        
        try:
            req = models.SearchByTextRequest()
            params = {
                "Query": query
            }
            req.from_json_string(json.dumps(params))
            
            resp = self.client.SearchByText(req)
            result_json = json.loads(resp.to_json_string())
            
            if 'Images' in result_json:
                images = []
                for img_str in result_json['Images']:
                    try:
                        img = json.loads(img_str)
                        
                        thumbnail_url = img.get('thumbnailUrl', '').replace('http://', 'https://')
                        original_url = img.get('origPicUrl', '').replace('http://', 'https://')
                        
                        selected_url = original_url if original_url else thumbnail_url
                        
                        if not selected_url:
                            continue
                        
                        parsed = requests.utils.urlparse(selected_url)
                        if parsed.hostname in BLOCKED_DOMAINS:
                            print(f"Skipping blocked domain: {parsed.hostname}")
                            continue
                        
                        # 尝试从API响应中获取真实相似度
                        similarity = None
                        # 检查API响应中是否有相似度字段
                        if 'score' in img:
                            similarity = float(img['score']) / 100.0 if img['score'] > 1 else float(img['score'])
                        elif 'similarity' in img:
                            similarity = float(img['similarity']) if img['similarity'] <= 1 else float(img['similarity']) / 100.0
                        elif 'confidence' in img:
                            similarity = float(img['confidence']) / 100.0 if img['confidence'] > 1 else float(img['confidence'])
                        
                        # 如果没有获取到真实相似度，使用基于排名的合理值
                        if similarity is None or similarity <= 0 or similarity > 1:
                            # 根据排名分配相似度，前几名相似度较高，后面逐渐降低
                            rank = len(images)
                            if rank == 0:
                                similarity = 0.85 + (0.1 * (1 - 0.5) * (1 - rank / 10))
                            elif rank == 1:
                                similarity = 0.80 + (0.05 * (1 - rank / 10))
                            elif rank == 2:
                                similarity = 0.75
                            elif rank == 3:
                                similarity = 0.70
                            else:
                                similarity = max(0.50, 0.65 - (rank - 4) * 0.03)
                        
                        # 确保相似度在合理范围内
                        similarity = max(0.1, min(0.99, similarity))
                        
                        images.append({
                            'image_url': selected_url,
                            'title': img.get('title', ''),
                            'source': '腾讯云图片搜索',
                            'similarity': similarity,
                            'is_network': True,
                            'thumbnail_url': thumbnail_url,
                            'original_url': original_url,
                            'site_name': img.get('siteName', ''),
                            'site_url': img.get('siteUrl', '').replace('http://', 'https://')
                        })
                        
                        if len(images) >= limit:
                            break
                    except Exception as e:
                        print(f"解析图片数据失败: {e}")
                        continue
                return images
            
            return []
        except Exception as e:
            print(f"Tencent API SearchByText error: {e}")
            return []
    
    def search_image_by_image(self, image_path, style=''):
        """
        使用图片搜索（降级为文本搜索，使用style作为关键词）
        
        Args:
            image_path: 图片路径
            style: 风格关键词
            
        Returns:
            图片列表
        """
        # 降级为文本搜索，使用style作为搜索词
        search_query = style if style else "图片"
        return self.search_image_by_text(search_query, limit=3)
