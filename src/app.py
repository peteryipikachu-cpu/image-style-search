import os
import sys
import json
import requests
from flask import Flask, request, jsonify, send_from_directory, redirect, Response
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from style_matcher import StyleMatcher
from aliyun_oss import oss_client

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

matcher = None
db_config = {
    'dbname': 'pikachu',
    'user': 'postgres',
    'password': '',
    'host': 'localhost',
    'port': '5432'
}

def init_matcher(use_db=True):
    global matcher
    matcher = StyleMatcher(
        Config.PARQUET_FILE, 
        Config.DATA_DIR, 
        db_config=db_config, 
        use_db=use_db,
        use_network_search=Config.USE_TENCENT_SEARCH,
        secret_id=Config.TENCENT_SECRET_ID,
        secret_key=Config.TENCENT_SECRET_KEY,
        doubao_api_key=Config.DOUBAO_API_KEY,
        doubao_model_id=Config.DOUBAO_MODEL_ID
    )
    print("Matcher initialized successfully")

@app.route('/api/analyze', methods=['GET'])
def analyze_badcases():
    if not matcher:
        return jsonify({'error': 'Matcher not initialized'}), 500
    
    try:
        results = matcher.analyze_all_badcases()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze/<case_name>', methods=['GET'])
def analyze_case(case_name):
    if not matcher:
        return jsonify({'error': 'Matcher not initialized'}), 500
    
    try:
        case_path = os.path.join(Config.DATA_DIR, case_name)
        if not os.path.isdir(case_path):
            return jsonify({'error': 'Case not found'}), 404
        
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        result = matcher.analyze_badcase(case_path, force_refresh=force_refresh)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh_network/<case_name>', methods=['POST'])
def refresh_network_search(case_name):
    if not matcher:
        return jsonify({'error': 'Matcher not initialized'}), 500
    
    try:
        result = matcher.refresh_network_search(case_name)
        if 'error' in result:
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh_generated/<case_name>', methods=['POST'])
def refresh_generated_images(case_name):
    if not matcher:
        return jsonify({'error': 'Matcher not initialized'}), 500
    
    try:
        result = matcher.refresh_generated_images(case_name)
        if 'error' in result:
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/find_reference', methods=['POST'])
def find_reference():
    if not matcher:
        return jsonify({'error': 'Matcher not initialized'}), 500
    
    try:
        data = request.json
        image_path = data.get('image_path')
        style = data.get('style', '')
        top_k = data.get('top_k', 5)
        by_result = data.get('by_result', True)
        
        if not image_path or not os.path.exists(image_path):
            return jsonify({'error': 'Invalid image path'}), 400
        
        if by_result:
            results = matcher.find_best_reference_by_result(image_path, style, top_k)
        else:
            results = matcher.find_best_reference(image_path, style, top_k)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/image/<case_name>/<filename>')
def serve_image_by_case(case_name, filename):
    try:
        case_dir = os.path.join(Config.DATA_DIR, case_name)
        file_path = os.path.join(case_dir, filename)
        
        if os.path.exists(file_path):
            return send_from_directory(case_dir, filename)
        
        return jsonify({'error': 'Image not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generated_images/<path:subpath>')
def serve_generated_image(subpath):
    """服务本地生成的图片"""
    try:
        # 构建完整路径
        base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'generated_images')
        file_path = os.path.join(base_dir, subpath)
        
        # 安全检查：确保路径在base_dir内
        real_path = os.path.realpath(file_path)
        real_base = os.path.realpath(base_dir)
        if not real_path.startswith(real_base):
            return jsonify({'error': 'Invalid path'}), 403
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            return send_from_directory(directory, filename)
        
        return jsonify({'error': 'Generated image not found'}), 404
    except Exception as e:
        print(f"Generated image error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/oss/<path:oss_path>')
def serve_oss_image(oss_path):
    try:
        if not oss_client.bucket:
            return jsonify({'error': 'OSS credentials not configured'}), 503
        
        signed_url = oss_client.generate_signed_url(oss_path, expiration=3600)
        if signed_url:
            return redirect(signed_url)
        else:
            oss_url = oss_client.get_file_url(oss_path)
            if oss_url:
                return redirect(oss_url)
            return jsonify({'error': 'OSS image not found'}), 404
    except Exception as e:
        print(f"OSS error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/proxy/image')
def proxy_image():
    try:
        image_url = request.args.get('url')
        if not image_url:
            return jsonify({'error': 'Missing URL parameter'}), 400
        
        if not image_url.startswith(('http://', 'https://')):
            return jsonify({'error': 'Invalid URL'}), 400
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Referer': '',
            'Origin': '',
        }
        
        try:
            response = requests.get(image_url, headers=headers, stream=True, timeout=10)
        except requests.exceptions.RequestException:
            headers['Referer'] = get_referer_from_url(image_url)
            response = requests.get(image_url, headers=headers, stream=True, timeout=10)
        
        if response.status_code != 200:
            print(f"Proxy image failed: {image_url} -> {response.status_code}")
            return jsonify({'error': f'Failed to fetch image: {response.status_code}'}), response.status_code
        
        content_type = response.headers.get('content-type', 'image/jpeg')
        return Response(response.content, content_type=content_type)
    
    except Exception as e:
        print(f"Proxy image error: {e}")
        return jsonify({'error': str(e)}), 500

def get_referer_from_url(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


@app.route('/api/cases', methods=['GET'])
def list_cases():
    try:
        case_dirs = sorted([d for d in os.listdir(Config.DATA_DIR) if os.path.isdir(os.path.join(Config.DATA_DIR, d))])
        return jsonify(case_dirs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/cases/<case_name>/info', methods=['GET'])
def get_case_info(case_name):
    try:
        case_path = os.path.join(Config.DATA_DIR, case_name)
        if not os.path.isdir(case_path):
            return jsonify({'error': 'Case not found'}), 404
        
        image_paths = matcher._get_image_paths_from_case(case_path)
        metadata = matcher._load_badcase_metadata(case_path)
        style = metadata.get('Style', metadata.get('Target Style', 'Unknown'))
        
        return jsonify({
            'case_name': case_name,
            'style': style,
            'image_paths': image_paths
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    return send_from_directory(static_dir, 'index.html')

try:
    init_matcher(use_db=os.getenv('USE_DB', 'True').lower() == 'true')
except Exception as e:
    print(f"Failed to initialize matcher at startup: {e}")
    import traceback
    traceback.print_exc()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
