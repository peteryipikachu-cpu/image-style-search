import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DEBUG = os.getenv('DEBUG', False)
    SECRET_KEY = os.getenv('SECRET_KEY', 'secret_key')
    DATA_DIR = os.getenv('DATA_DIR', '/Users/pikachu/work/bodeng/yitusoutu/以图搜图_badcase')
    PARQUET_FILE = os.getenv('PARQUET_FILE', '/Users/pikachu/work/bodeng/yitusoutu/ps_image_9138446_part00.parquet')
    CLIP_MODEL = os.getenv('CLIP_MODEL', 'ViT-B/32')
    PORT = int(os.getenv('PORT', 5000))
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    TENCENT_SECRET_ID = os.getenv('TENCENT_SECRET_ID', '')
    TENCENT_SECRET_KEY = os.getenv('TENCENT_SECRET_KEY', '')
    USE_TENCENT_SEARCH = os.getenv('USE_TENCENT_SEARCH', 'False').lower() == 'true'
    
    ALIYUN_OSS_ACCESS_KEY_ID = os.getenv('ALIYUN_OSS_ACCESS_KEY_ID', '')
    ALIYUN_OSS_ACCESS_KEY_SECRET = os.getenv('ALIYUN_OSS_ACCESS_KEY_SECRET', '')
    ALIYUN_OSS_ENDPOINT = os.getenv('ALIYUN_OSS_ENDPOINT', 'oss-cn-hangzhou.aliyuncs.com')
    ALIYUN_OSS_BUCKET = os.getenv('ALIYUN_OSS_BUCKET', '')
    
    # 豆包API配置
    DOUBAO_API_KEY = os.getenv('DOUBAO_API_KEY', '')
    DOUBAO_MODEL_ID = os.getenv('DOUBAO_MODEL_ID', 'doubao-seed-2-0-lite-260428')
    
    @staticmethod
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS