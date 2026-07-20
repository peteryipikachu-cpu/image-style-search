#!/usr/bin/env python3
"""
Parquet图片预向量化脚本
将parquet文件中的图片提取特征向量并存储到PostgreSQL数据库
支持从阿里云OSS下载图片
"""

import sys
import os
import psycopg2
import tempfile
from pgvector.psycopg2 import register_vector
import pandas as pd
import torch
import clip
from PIL import Image
import numpy as np
from tqdm import tqdm
import time

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.aliyun_oss import oss_client

# 配置
PARQUET_FILE = '/Users/pikachu/work/bodeng/yitusoutu/ps_image_9138446_part00.parquet'
BATCH_SIZE = 1000
LIMIT = None  # None表示处理全部，或设置数字如1000

DB_CONFIG = {
    'dbname': 'pikachu',
    'user': 'postgres',
    'host': 'localhost',
    'port': '5432'
}

def init_clip():
    """初始化CLIP模型"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading CLIP model on {device}...")
    model, preprocess = clip.load("ViT-B/32", device=device)
    model.eval()
    return model, preprocess, device

def extract_image_features_from_local(model, preprocess, image_path, device):
    """从本地文件提取图片特征向量"""
    try:
        if not os.path.exists(image_path):
            return None
        
        image = Image.open(image_path).convert("RGB")
        image_input = preprocess(image).unsqueeze(0).to(device)
        
        with torch.no_grad():
            features = model.encode_image(image_input)
        
        features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().numpy().flatten()
    except Exception as e:
        return None

def extract_image_features_from_oss(model, preprocess, oss_path, device):
    """从OSS下载图片并提取特征向量"""
    try:
        if not oss_client.bucket:
            return None
        
        oss_key = oss_path
        if oss_path.startswith('blink-edge/'):
            oss_key = oss_path.replace('blink-edge/', '', 1)
        
        if not oss_client.file_exists(oss_key):
            return None
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            if oss_client.download_file(oss_key, tmp_path):
                features = extract_image_features_from_local(model, preprocess, tmp_path, device)
                return features
            return None
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        return None

def extract_text_features(model, text, device):
    """提取文本特征向量"""
    try:
        if not text or len(text.strip()) == 0:
            return None
        
        text_input = clip.tokenize([text], truncate=True).to(device)
        
        with torch.no_grad():
            features = model.encode_text(text_input)
        
        features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().numpy().flatten()
    except Exception as e:
        return None

def init_database():
    """初始化数据库"""
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)
    cur = conn.cursor()
    
    print("Creating vector extension...")
    cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    print("Creating table...")
    cur.execute('''
        CREATE TABLE IF NOT EXISTS image_features (
            id SERIAL PRIMARY KEY,
            image_id VARCHAR(255) UNIQUE NOT NULL,
            file_path TEXT NOT NULL,
            file_name VARCHAR(255),
            category VARCHAR(255),
            image_desc TEXT,
            keywords TEXT,
            image_phash VARCHAR(64),
            origin_category VARCHAR(255),
            project_flag VARCHAR(255),
            image_vector vector(512),
            text_vector vector(512),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    print("Creating indexes...")
    cur.execute('CREATE INDEX IF NOT EXISTS idx_image_id ON image_features(image_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_category ON image_features(category)')
    
    conn.commit()
    
    cur.execute('SELECT COUNT(*) FROM image_features')
    count = cur.fetchone()[0]
    print(f"Current records in database: {count}")
    
    return conn, cur

def insert_metadata_batch(conn, cur, records):
    """批量插入元数据（不带向量）"""
    if not records:
        return 0
    
    try:
        placeholders = ', '.join(['%s'] * len(records))
        cur.execute(f'''
            INSERT INTO image_features 
            (image_id, file_path, file_name, category, image_desc, keywords, 
             image_phash, origin_category, project_flag)
            VALUES {placeholders}
            ON CONFLICT (image_id) DO UPDATE SET
                file_path = EXCLUDED.file_path,
                file_name = EXCLUDED.file_name,
                category = EXCLUDED.category,
                image_desc = EXCLUDED.image_desc,
                keywords = EXCLUDED.keywords
        ''', records)
        conn.commit()
        return len(records)
    except Exception as e:
        print(f"Error inserting batch: {e}")
        conn.rollback()
        return 0

def update_vectors_batch(conn, cur, updates):
    """批量更新向量"""
    if not updates:
        return 0
    
    success_count = 0
    for image_id, image_vector, text_vector in updates:
        try:
            cur.execute('''
                UPDATE image_features 
                SET image_vector = %s::vector, text_vector = %s::vector
                WHERE image_id = %s
            ''', (image_vector.tolist(), text_vector.tolist() if text_vector is not None else None, image_id))
            success_count += 1
        except Exception as e:
            pass
    
    if success_count > 0:
        conn.commit()
    return success_count

def main(limit=None, metadata_only=False):
    print("=" * 70)
    print("Image Vectorization Tool - Parquet Processing")
    print("=" * 70)
    
    # 连接数据库
    conn, cur = init_database()
    
    # 读取parquet
    print(f"\nLoading parquet file: {PARQUET_FILE}")
    df = pd.read_parquet(PARQUET_FILE)
    
    if limit:
        df = df.head(limit)
        print(f"Processing limited to {limit} records")
    
    print(f"Total records to process: {len(df)}")
    
    # 步骤1：批量插入元数据
    print("\n[Step 1/2] Inserting metadata...")
    metadata_batch = []
    total_inserted = 0
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Inserting metadata"):
        try:
            image_id = row['image_id']
            file_path = row['file_path']
            file_name = row.get('file_name', '')
            category = row.get('category', '')
            keywords = row.get('keywords', '')
            image_desc = row.get('image_desc', '')
            image_phash = row.get('image_phash', '')
            origin_category = row.get('origin_category', '')
            project_flag = row.get('project_flag', '')
            
            metadata_batch.append((image_id, file_path, file_name, category, 
                                 image_desc, keywords, image_phash, 
                                 origin_category, project_flag))
            
            if len(metadata_batch) >= BATCH_SIZE:
                total_inserted += insert_metadata_batch(conn, cur, metadata_batch)
                metadata_batch = []
        
        except Exception as e:
            pass
    
    if metadata_batch:
        total_inserted += insert_metadata_batch(conn, cur, metadata_batch)
    
    print(f"\nSuccessfully inserted {total_inserted} metadata records")
    
    # 如果只需要元数据，跳过向量提取
    if metadata_only:
        print("\nSkipping vector extraction (metadata-only mode)")
        cur.execute('CREATE INDEX IF NOT EXISTS idx_image_vector ON image_features USING ivfflat (image_vector vector_cosine_ops)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_text_vector ON image_features USING ivfflat (text_vector vector_cosine_ops)')
        conn.commit()
        
        cur.execute('SELECT COUNT(*) FROM image_features')
        total_count = cur.fetchone()[0]
        print(f"\nTotal records in database: {total_count}")
        
        cur.close()
        conn.close()
        return
    
    # 步骤2：提取向量
    if not oss_client.bucket:
        print("\nERROR: OSS client not initialized. Cannot extract image vectors.")
        cur.close()
        conn.close()
        return
    
    print("\n[Step 2/2] Extracting vectors...")
    print(f"OSS client initialized: {oss_client.bucket is not None}")
    model, preprocess, device = init_clip()
    
    # 获取需要更新向量的记录
    if limit:
        cur.execute(f'''
            SELECT id, image_id, file_path, category, keywords, image_desc 
            FROM image_features 
            WHERE image_vector IS NULL AND file_path LIKE 'blink-edge/%'
            LIMIT {limit}
        ''')
    else:
        cur.execute('''
            SELECT id, image_id, file_path, category, keywords, image_desc 
            FROM image_features 
            WHERE image_vector IS NULL AND file_path LIKE 'blink-edge/%'
        ''')
    records_to_update = cur.fetchall()
    
    print(f"Records to vectorize: {len(records_to_update)}")
    
    updates_batch = []
    success_count = 0
    error_count = 0
    start_time = time.time()
    
    for idx, (record_id, image_id, file_path, category, keywords, image_desc) in enumerate(
            tqdm(records_to_update, desc="Vectorizing")):
        try:
            # 从OSS下载并提取图片特征
            image_vector = extract_image_features_from_oss(model, preprocess, file_path, device)
            
            if image_vector is None:
                error_count += 1
                continue
            
            # 提取文本特征
            combined_text = f"{category}. {keywords}. {image_desc}".strip()
            text_vector = extract_text_features(model, combined_text, device)
            
            updates_batch.append((image_id, image_vector, text_vector))
            
            if len(updates_batch) >= BATCH_SIZE:
                success_count += update_vectors_batch(conn, cur, updates_batch)
                updates_batch = []
                
                elapsed = time.time() - start_time
                rate = success_count / elapsed
                remaining = (len(records_to_update) - idx - 1) / rate if rate > 0 else 0
                print(f"\n  Progress: {success_count}/{len(records_to_update)} "
                      f"({success_count / len(records_to_update) * 100:.1f}%) "
                      f"- Rate: {rate:.1f} img/s - ETA: {remaining/60:.1f} min")
        
        except Exception as e:
            error_count += 1
    
    if updates_batch:
        success_count += update_vectors_batch(conn, cur, updates_batch)
    
    # 添加向量索引
    print("\nAdding vector indexes...")
    cur.execute('CREATE INDEX IF NOT EXISTS idx_image_vector ON image_features USING ivfflat (image_vector vector_cosine_ops)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_text_vector ON image_features USING ivfflat (text_vector vector_cosine_ops)')
    conn.commit()
    
    # 统计
    elapsed = time.time() - start_time
    cur.execute('SELECT COUNT(*) FROM image_features')
    total_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM image_features WHERE image_vector IS NOT NULL')
    vector_count = cur.fetchone()[0]
    
    print("\n" + "=" * 70)
    print("Processing Complete!")
    print("=" * 70)
    print(f"Total records in database: {total_count}")
    print(f"Records with vectors: {vector_count}")
    print(f"Time elapsed for vectorization: {elapsed/60:.2f} minutes")
    print(f"Processing rate: {success_count/elapsed:.2f} images/second")
    print(f"Successfully processed: {success_count}")
    print(f"Errors: {error_count}")
    print("=" * 70)
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Vectorize images from parquet file')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of records to process')
    parser.add_argument('--metadata-only', action='store_true', help='Only insert metadata, skip vector extraction')
    args = parser.parse_args()
    
    main(limit=args.limit, metadata_only=args.metadata_only)
