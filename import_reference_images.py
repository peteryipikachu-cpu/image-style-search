#!/usr/bin/env python3
import os
import glob
from src.database import Database
from src.feature_extractor import FeatureExtractor
from src.image_captioner import ImageCaptioner

def import_reference_images(directory, db, extractor, captioner):
    """导入参考图到数据库"""
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    
    # 扫描所有图片
    image_paths = []
    for ext in image_extensions:
        image_paths.extend(glob.glob(f'{directory}/**/*{ext}', recursive=True))
    
    print(f'Found {len(image_paths)} reference images')
    
    # 获取目录结构作为category
    categories = set()
    for path in image_paths:
        rel_path = os.path.relpath(path, directory)
        parts = rel_path.split(os.sep)
        if len(parts) > 1:
            categories.add(parts[0])
    
    print(f'Categories: {categories}')
    
    # 处理每张图片
    for idx, image_path in enumerate(image_paths):
        try:
            image_id = os.path.splitext(os.path.basename(image_path))[0]
            category = os.path.basename(os.path.dirname(image_path))
            
            # 检查是否已存在
            existing = db.search_by_keywords(image_id, top_k=1)
            if existing and existing[0]['image_id'] == image_id:
                print(f'Skipping existing: {image_id}')
                continue
            
            print(f'Processing {idx+1}/{len(image_paths)}: {os.path.basename(image_path)}')
            
            # 提取特征（这里不需要，文本搜索不需要向量）
            # image_vector = extractor.extract_image_features(image_path)
            
            # 生成图片描述
            image_desc = captioner.generate_caption(image_path, category)
            
            # 生成关键词（使用category）
            keywords = category
            
            # 插入数据库（不包含向量）
            db.insert_image_feature(
                image_id=image_id,
                file_path=image_path,
                file_name=os.path.basename(image_path),
                category=category,
                image_desc=image_desc,
                keywords=keywords,
                image_vector=None,  # 文本搜索不需要向量
                text_vector=None
            )
            
        except Exception as e:
            print(f'Error processing {image_path}: {e}')
    
    print(f'\nImport complete! Total records in database: {db.get_count()}')

if __name__ == '__main__':
    # 初始化数据库
    db = Database()
    db.init_database()
    
    # 初始化特征提取器和captioner
    extractor = FeatureExtractor()
    captioner = ImageCaptioner()
    
    # 参考图目录 - 从以图搜图_badcase目录中的"参考图"文件导入
    badcase_dir = './以图搜图_badcase'
    
    if os.path.exists(badcase_dir):
        print(f'Importing reference images from {badcase_dir}...')
        
        # 扫描所有case目录，收集"参考图"文件
        import glob
        import json
        ref_images = []
        for case_dir in glob.glob(f'{badcase_dir}/case_*'):
            for ref_file in glob.glob(f'{case_dir}/*参考图*'):
                if any(ref_file.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']):
                    ref_images.append((case_dir, ref_file))
        
        print(f'Found {len(ref_images)} reference images')
        
        # 清空数据库
        print('Clearing existing database records...')
        # PostgreSQL 使用 TRUNCATE 清空表
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('TRUNCATE TABLE image_features RESTART IDENTITY')
            conn.commit()
        
        # 处理每张参考图
        for idx, (case_dir_path, image_path) in enumerate(ref_images):
            try:
                case_name = os.path.basename(case_dir_path)
                image_id = os.path.splitext(os.path.basename(image_path))[0]
                
                # 从metadata中读取style
                metadata_path = os.path.join(case_dir_path, f'{case_name}_metadata.json')
                keywords = case_name  # 默认值
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        keywords = metadata.get('Style', metadata.get('Target Style', case_name))
                
                print(f'Processing {idx+1}/{len(ref_images)}: {os.path.basename(image_path)}')
                print(f'  Style: {keywords}')
                
                # 生成图片描述
                image_desc = captioner.generate_caption(image_path, keywords)
                
                # 提取图片向量（CLIP向量搜索需要）
                print(f'  Extracting image vector using CLIP...')
                image_vector = extractor.extract_image_features(image_path)
                if image_vector is None:
                    print(f'  ⚠️ Failed to extract image vector')
                    image_vector = None
                else:
                    print(f'  ✅ Image vector extracted: shape = {image_vector.shape}')
                
                # 提取文本向量（用于文本到图片的向量搜索）
                print(f'  Extracting text vector for keywords...')
                text_vector = extractor.extract_text_features(keywords)
                if text_vector is None:
                    print(f'  ⚠️ Failed to extract text vector')
                    text_vector = None
                else:
                    print(f'  ✅ Text vector extracted: shape = {text_vector.shape}')
                
                # 插入数据库（包含向量）
                db.insert_image_feature(
                    image_id=image_id,
                    file_path=image_path,
                    file_name=os.path.basename(image_path),
                    category=case_name,
                    image_desc=image_desc,
                    keywords=keywords,
                    image_vector=image_vector,
                    text_vector=text_vector
                )
                
            except Exception as e:
                print(f'Error processing {image_path}: {e}')
                import traceback
                traceback.print_exc()
        
        print(f'\nImport complete! Total records in database: {db.get_count()}')
    else:
        print(f'Directory not found: {badcase_dir}')
