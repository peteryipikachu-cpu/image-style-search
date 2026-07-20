import os
import sys
import json
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feature_extractor import FeatureExtractor
from database import Database
from tencent_image_search import TencentImageSearch
from image_captioner import ImageCaptioner

class StyleMatcher:
    def __init__(self, parquet_file: str, data_dir: str, db_config=None, use_db=False, use_network_search=False, secret_id=None, secret_key=None, doubao_api_key=None, doubao_model_id=None):
        self.parquet_file = parquet_file
        self.data_dir = data_dir
        self.use_db = use_db
        self.use_network_search = use_network_search
        self.extractor = FeatureExtractor()
        self.captioner = ImageCaptioner(doubao_api_key=doubao_api_key, doubao_model_id=doubao_model_id)
        self.db = Database(db_config=db_config) if use_db else None
        if self.db:
            self.db.init_database()
        self.image_data = self._load_image_data() if not use_db else None
        self._cache_all_badcase_images()
        
        self.cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        if use_network_search and secret_id and secret_key:
            self.network_search_client = TencentImageSearch(secret_id, secret_key)
            print("Using real Tencent Cloud Image Search API")
        elif use_network_search:
            print("Using real Tencent Cloud Image Search (credentials from env)")
            self.network_search_client = TencentImageSearch(secret_id or '', secret_key or '')
        else:
            self.network_search_client = None
    
    def _cache_all_badcase_images(self):
        """Cache all images from badcase directory for search"""
        self.cached_images = []
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if os.path.splitext(file)[1].lower() in image_extensions:
                    image_path = os.path.join(root, file)
                    feat = self.extractor.extract_image_features(image_path)
                    if feat is not None:
                        self.cached_images.append({
                            'image_id': os.path.splitext(file)[0],
                            'file_path': image_path,
                            'file_name': file,
                            'category': os.path.basename(root),
                            'features': feat
                        })
        
        print(f"Cached {len(self.cached_images)} images from badcase directory")
    
    def _load_image_data(self) -> pd.DataFrame:
        try:
            df = pd.read_parquet(self.parquet_file)
            return df
        except Exception as e:
            print(f"Error loading parquet file: {e}")
            return pd.DataFrame()
    
    def _load_badcase_metadata(self, case_dir: str) -> dict:
        metadata_path = os.path.join(case_dir, f"{os.path.basename(case_dir)}_metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                return json.load(f)
        return {}
    
    def _get_image_paths_from_case(self, case_dir: str) -> dict:
        paths = {}
        case_name = os.path.basename(case_dir)
        
        for fname in os.listdir(case_dir):
            if '原图' in fname:
                paths['original'] = os.path.join(case_dir, fname)
            elif '参考图' in fname:
                paths['reference'] = os.path.join(case_dir, fname)
            elif '结果图' in fname:
                paths['result'] = os.path.join(case_dir, fname)
        
        return paths
    
    def calculate_similarity(self, feat1: np.ndarray, feat2: np.ndarray) -> float:
        if feat1 is None or feat2 is None:
            return 0.0
        return cosine_similarity([feat1], [feat2])[0][0]
    
    def _get_cache_path(self, case_name: str, cache_type: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{case_name}_{cache_type}.json")
    
    def _load_cache(self, case_name: str, cache_type: str) -> dict:
        """加载缓存"""
        cache_path = self._get_cache_path(case_name, cache_type)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Failed to load cache {cache_path}: {e}")
        return None
    
    def _save_cache(self, case_name: str, cache_type: str, data: dict):
        """保存缓存"""
        cache_path = self._get_cache_path(case_name, cache_type)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved: {cache_path}")
        except Exception as e:
            print(f"Failed to save cache {cache_path}: {e}")
    
    def _clear_cache(self, case_name: str, cache_type: str = None):
        """清除缓存"""
        if cache_type:
            cache_path = self._get_cache_path(case_name, cache_type)
            if os.path.exists(cache_path):
                os.remove(cache_path)
                print(f"Cache cleared: {cache_path}")
        else:
            for ct in ['network', 'generated']:
                cache_path = self._get_cache_path(case_name, ct)
                if os.path.exists(cache_path):
                    os.remove(cache_path)
    
    def find_best_reference_by_result(self, result_path: str, style: str, top_k: int = 5) -> list:
        """
        使用CLIP向量搜索查找本地参考图，如果没有向量数据则fallback到关键词搜索
        
        Args:
            result_path: 结果图路径（用于提取图片向量）
            style: 风格关键词（用于提取文本向量）
            top_k: 返回数量
            
        Returns:
            按相似度排序的参考图列表
        """
        if self.use_db and self.db:
            try:
                # 使用CLIP提取文本特征向量
                print(f"\n=== Searching local reference images using CLIP text-to-image search ===")
                print(f"Style keywords: {style}")
                
                # 提取文本特征向量
                text_features = self.extractor.extract_text_features(style)
                if text_features is None:
                    print("❌ Failed to extract text features, falling back to keyword search")
                    return self.db.search_by_keywords(style, top_k=top_k)
                
                print(f"✅ Text features extracted: shape = {text_features.shape}")
                
                # 使用文本特征向量搜索图片
                results = self.db.search_by_text_vector(text_features, top_k=top_k)
                
                print(f"✅ CLIP vector search returned {len(results)} results")
                
                # 检查向量搜索结果是否有效（相似度是否大于0）
                has_valid_results = any(r.get('combined_score', 0) > 0 for r in results)
                
                if has_valid_results:
                    if results:
                        print(f"   Top 1: {results[0].get('file_name', 'N/A')} (similarity: {results[0].get('combined_score', 0):.4f})")
                    return results
                else:
                    print("⚠️ Vector search returned no valid results (all similarities are 0), falling back to keyword search")
                    return self.db.search_by_keywords(style, top_k=top_k)
                
            except Exception as e:
                print(f"❌ CLIP vector search failed: {e}, falling back to keyword search")
                try:
                    return self.db.search_by_keywords(style, top_k=top_k)
                except Exception as fallback_e:
                    print(f"❌ Keyword search also failed: {fallback_e}")
                    import traceback
                    traceback.print_exc()
                    return []
        
        return []
    
    def search_network_images(self, image_path: str, style: str, top_k: int = 3, extra_keywords='') -> dict:
        if not self.network_search_client:
            return {'caption': '', 'keywords': [], 'search_query': '', 'results': []}
        
        try:
            search_query = style if style else '设计 参考图片'
            keywords = [style] if style else []
            
            print(f"\n=== Searching network images with style: {search_query} ===")
            print(f"Search query sent to Tencent: {search_query}")
            print("=" * 80 + "\n")
            
            results = self.network_search_client.search_image_by_text(search_query, limit=top_k)
            
            if results and image_path:
                results = self._calculate_network_image_similarity(results, image_path)
            
            return {
                'caption': '',
                'keywords': keywords,
                'search_query': search_query,
                'results': results[:top_k]
            }
        except Exception as e:
            print(f"Network search error: {e}")
            fallback_query = style if style else '设计 参考图片'
            print(f"Falling back to search query: {fallback_query}")
            try:
                results = self.network_search_client.search_image_by_text(fallback_query, limit=top_k)
                
                if results and image_path:
                    results = self._calculate_network_image_similarity(results, image_path)
                
                return {
                    'caption': '',
                    'keywords': [style] if style else [],
                    'search_query': fallback_query,
                    'results': results[:top_k]
                }
            except:
                return {'caption': '', 'keywords': [], 'search_query': '', 'results': []}
    
    def _calculate_network_image_similarity(self, network_results, result_image_path):
        """对网络搜索结果图片进行向量化，并与结果图计算真实相似度"""
        try:
            import requests
            from PIL import Image
            from io import BytesIO
            
            print(f"\n=== Calculating real similarity for network images ===")
            
            result_feat = self.extractor.extract_image_features(result_image_path)
            if result_feat is None:
                print("Failed to extract result image features")
                return network_results
            
            updated_results = []
            for idx, result in enumerate(network_results):
                img_url = result.get('image_url', '')
                if not img_url:
                    updated_results.append(result)
                    continue
                
                try:
                    response = requests.get(img_url, timeout=10)
                    if response.status_code != 200:
                        print(f"Failed to download image: {img_url}")
                        updated_results.append(result)
                        continue
                    
                    img = Image.open(BytesIO(response.content))
                    network_feat = self.extractor.extract_image_features_from_pil(img)
                    
                    if network_feat is None:
                        print(f"Failed to extract feature for image: {img_url}")
                        updated_results.append(result)
                        continue
                    
                    similarity = self.calculate_similarity(result_feat, network_feat)
                    result['similarity'] = float(similarity)
                    result['similarity_source'] = 'CLIP_vector'
                    
                    print(f"Image {idx+1}: {img_url} -> similarity = {similarity:.4f}")
                    updated_results.append(result)
                    
                except Exception as e:
                    print(f"Error calculating similarity for {img_url}: {e}")
                    updated_results.append(result)
            
            updated_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
            print(f"=== Finished calculating similarities ===")
            
            return updated_results
            
        except Exception as e:
            print(f"Error in _calculate_network_image_similarity: {e}")
            import traceback
            traceback.print_exc()
            return network_results
    
    def _regenerate_network_search(self, case_name: str, case_path: str, style: str) -> dict:
        """重新执行网络搜索（不使用缓存）"""
        metadata = self._load_badcase_metadata(case_path)
        paths = self._get_image_paths_from_case(case_path)
        
        extra_keywords = []
        if 'Category' in metadata:
            extra_keywords.append(metadata['Category'])
        if 'Keywords' in metadata:
            extra_keywords.append(metadata['Keywords'])
        if 'ImageDescription' in metadata:
            extra_keywords.append(metadata['ImageDescription'])
        
        extra_keywords_str = ' '.join(extra_keywords)
        network_result = self.search_network_images(
            paths.get('result'), 
            style, 
            top_k=3, 
            extra_keywords=extra_keywords_str
        )
        
        cache_data = {
            'caption': network_result.get('caption', ''),
            'keywords': network_result.get('keywords', []),
            'search_query': network_result.get('search_query', ''),
            'results': network_result.get('results', []),
            'cached_at': pd.Timestamp.now().isoformat()
        }
        
        self._save_cache(case_name, 'network', cache_data)
        return cache_data
    
    def _regenerate_images(self, case_name: str, case_path: str, style: str, network_caption: str = '') -> dict:
        """重新生成图片（不使用缓存）"""
        generation_result = self.captioner.generate_text_to_image(
            style,
            network_caption,
            num_images=3,
            case_name=case_name
        )
        
        cache_data = {
            'images': generation_result.get('images', []),
            'prompt': generation_result.get('prompt', ''),
            'error': generation_result.get('error', None),
            'cached_at': pd.Timestamp.now().isoformat()
        }
        
        self._save_cache(case_name, 'generated', cache_data)
        return cache_data
    
    def analyze_badcase(self, case_dir: str, force_refresh: bool = False) -> dict:
        metadata = self._load_badcase_metadata(case_dir)
        paths = self._get_image_paths_from_case(case_dir)
        case_name = os.path.basename(case_dir)
        style = metadata.get('Style', '')
        
        original_feat = self.extractor.extract_image_features(paths.get('original'))
        reference_feat = self.extractor.extract_image_features(paths.get('reference'))
        result_feat = self.extractor.extract_image_features(paths.get('result'))
        style_feat = self.extractor.extract_text_features(style)
        
        local_references = self.find_best_reference_by_result(paths.get('result'), style, top_k=3)
        
        if force_refresh:
            print(f"\n=== Force refreshing cache for {case_name} ===")
            self._clear_cache(case_name)
        
        network_cache = self._load_cache(case_name, 'network')
        if network_cache:
            print(f"\n=== Loading network search from cache for {case_name} ===")
            network_result = {
                'caption': network_cache.get('caption', ''),
                'keywords': network_cache.get('keywords', []),
                'search_query': network_cache.get('search_query', ''),
                'results': network_cache.get('results', [])
            }
        else:
            print(f"\n=== No cache found, performing network search for {case_name} ===")
            network_cache = self._regenerate_network_search(case_name, case_dir, style)
            network_result = {
                'caption': network_cache.get('caption', ''),
                'keywords': network_cache.get('keywords', []),
                'search_query': network_cache.get('search_query', ''),
                'results': network_cache.get('results', [])
            }
        
        generated_cache = self._load_cache(case_name, 'generated')
        if generated_cache:
            print(f"\n=== Loading generated images from cache for {case_name} ===")
            # 检查本地图片是否存在
            cached_images = generated_cache.get('images', [])
            valid_images = []
            for img_path in cached_images:
                # 如果是本地路径，检查文件是否存在
                if img_path.startswith('/generated_images/'):
                    full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                            img_path.lstrip('/'))
                    if os.path.exists(full_path):
                        valid_images.append(img_path)
                    else:
                        print(f"Cached image not found: {full_path}")
                else:
                    # 兼容旧版URL缓存
                    valid_images.append(img_path)
            
            generation_result = {
                'images': valid_images,
                'prompt': generated_cache.get('prompt', ''),
                'error': generated_cache.get('error', None) if valid_images else 'Cached images expired'
            }
            
            # 如果没有有效图片，清除缓存重新生成
            if not valid_images:
                print(f"No valid cached images, regenerating...")
                self._clear_cache(case_name, 'generated')
                generated_cache = None
        
        if not generated_cache:
            print(f"\n=== No cache found, generating images for {case_name} ===")
            generated_cache = self._regenerate_images(case_name, case_dir, style, network_result.get('caption', ''))
            generation_result = {
                'images': generated_cache.get('images', []),
                'prompt': generated_cache.get('prompt', ''),
                'error': generated_cache.get('error', None)
            }
        
        analysis = {
            'case_name': case_name,
            'metadata': metadata,
            'image_paths': paths,
            'style': style,
            'similarities': {
                'original_reference': float(self.calculate_similarity(original_feat, reference_feat)),
                'original_result': float(self.calculate_similarity(original_feat, result_feat)),
                'reference_result': float(self.calculate_similarity(reference_feat, result_feat)),
                'style_reference': float(self.calculate_similarity(style_feat, reference_feat)),
                'style_result': float(self.calculate_similarity(style_feat, result_feat))
            },
            'suggested_references': local_references,
            'result_caption': network_result.get('caption', ''),
            'search_keywords': network_result.get('keywords', []),
            'search_query': network_result.get('search_query', ''),
            'network_references': network_result.get('results', []),
            'generated_references': generation_result.get('images', []),
            'generation_prompt': generation_result.get('prompt', ''),
            'generation_error': generation_result.get('error', None)
        }
        
        return analysis
    
    def refresh_network_search(self, case_name: str) -> dict:
        """刷新网络搜索（不使用缓存）"""
        case_path = os.path.join(self.data_dir, case_name)
        if not os.path.isdir(case_path):
            return {'error': 'Case not found'}
        
        metadata = self._load_badcase_metadata(case_path)
        style = metadata.get('Style', '')
        
        print(f"\n=== Refreshing network search for {case_name} ===")
        self._clear_cache(case_name, 'network')
        
        network_cache = self._regenerate_network_search(case_name, case_path, style)
        
        return {
            'caption': network_cache.get('caption', ''),
            'keywords': network_cache.get('keywords', []),
            'search_query': network_cache.get('search_query', ''),
            'results': network_cache.get('results', [])
        }
    
    def refresh_generated_images(self, case_name: str) -> dict:
        """刷新生成的图片（不使用缓存）"""
        case_path = os.path.join(self.data_dir, case_name)
        if not os.path.isdir(case_path):
            return {'error': 'Case not found'}
        
        metadata = self._load_badcase_metadata(case_path)
        style = metadata.get('Style', '')
        
        network_cache = self._load_cache(case_name, 'network')
        network_caption = network_cache.get('caption', '') if network_cache else ''
        
        print(f"\n=== Refreshing generated images for {case_name} ===")
        self._clear_cache(case_name, 'generated')
        
        generated_cache = self._regenerate_images(case_name, case_path, style, network_caption)
        
        return {
            'images': generated_cache.get('images', []),
            'prompt': generated_cache.get('prompt', ''),
            'error': generated_cache.get('error', None)
        }
    
    def analyze_all_badcases(self) -> list:
        results = []
        case_dirs = sorted([d for d in os.listdir(self.data_dir) if os.path.isdir(os.path.join(self.data_dir, d))])
        
        for case_dir in case_dirs:
            full_path = os.path.join(self.data_dir, case_dir)
            analysis = self.analyze_badcase(full_path)
            results.append(analysis)
        
        return results
