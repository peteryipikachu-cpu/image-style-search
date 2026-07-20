import oss2
import os
import sys
from io import BytesIO

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

class AliyunOSS:
    def __init__(self):
        # 禁用代理，避免影响OSS连接
        os.environ['NO_PROXY'] = 'aliyuncs.com,.aliyuncs.com'
        os.environ['no_proxy'] = 'aliyuncs.com,.aliyuncs.com'
        
        self.access_key_id = Config.ALIYUN_OSS_ACCESS_KEY_ID
        self.access_key_secret = Config.ALIYUN_OSS_ACCESS_KEY_SECRET
        self.endpoint = Config.ALIYUN_OSS_ENDPOINT
        self.bucket_name = Config.ALIYUN_OSS_BUCKET
        self.bucket = None
        
        if self.access_key_id and self.access_key_secret and self.bucket_name:
            self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name,
                                      connect_timeout=30)
    
    def upload_file(self, file_path, oss_path):
        if not self.bucket:
            return None
        
        try:
            self.bucket.put_object_from_file(oss_path, file_path)
            return f'https://{self.bucket_name}.{self.endpoint}/{oss_path}'
        except Exception as e:
            print(f"OSS upload error: {e}")
            return None
    
    def upload_bytes(self, content, oss_path):
        if not self.bucket:
            return None
        
        try:
            if isinstance(content, BytesIO):
                content.seek(0)
                self.bucket.put_object(oss_path, content)
            else:
                self.bucket.put_object(oss_path, content)
            return f'https://{self.bucket_name}.{self.endpoint}/{oss_path}'
        except Exception as e:
            print(f"OSS upload error: {e}")
            return None
    
    def download_file(self, oss_path, local_path):
        if not self.bucket:
            return False
        
        try:
            self.bucket.get_object_to_file(oss_path, local_path)
            return True
        except Exception as e:
            print(f"OSS download error: {e}")
            return False
    
    def download_bytes(self, oss_path):
        if not self.bucket:
            return None
        
        try:
            result = self.bucket.get_object(oss_path)
            return result.read()
        except Exception as e:
            print(f"OSS download error: {e}")
            return None
    
    def delete_file(self, oss_path):
        if not self.bucket:
            return False
        
        try:
            self.bucket.delete_object(oss_path)
            return True
        except Exception as e:
            print(f"OSS delete error: {e}")
            return False
    
    def list_files(self, prefix='', max_keys=100):
        if not self.bucket:
            return []
        
        try:
            result = []
            for obj in oss2.ObjectIterator(self.bucket, prefix=prefix, max_keys=max_keys):
                result.append({
                    'name': obj.key,
                    'size': obj.size,
                    'last_modified': obj.last_modified
                })
            return result
        except Exception as e:
            print(f"OSS list error: {e}")
            return []
    
    def file_exists(self, oss_path):
        if not self.bucket:
            return False
        
        try:
            self.bucket.get_object_meta(oss_path)
            return True
        except oss2.exceptions.NoSuchKey:
            return False
        except Exception as e:
            print(f"OSS exists check error: {e}")
            return False
    
    def get_file_url(self, oss_path):
        if not self.bucket:
            return None
        
        return f'https://{self.bucket_name}.{self.endpoint}/{oss_path}'
    
    def generate_signed_url(self, oss_path, expiration=3600):
        if not self.bucket:
            return None
        
        try:
            return self.bucket.sign_url('GET', oss_path, expiration)
        except Exception as e:
            print(f"OSS signed url error: {e}")
            return None

oss_client = AliyunOSS()