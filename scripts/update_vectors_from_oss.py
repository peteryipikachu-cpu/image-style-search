#!/usr/bin/env python3
"""
从阿里OSS下载图片并更新数据库中的image_vector
"""

import sys
import os
import time
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from pgvector.psycopg2 import register_vector
import torch
import clip
from PIL import Image
import numpy as np
from tqdm import tqdm

from src.aliyun_oss import oss_client
from config import Config


def init_clip():
    """初始化CLIP模型"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading CLIP model on {device}...")
    model, preprocess = clip.load("ViT-B/32", device=device)
    model.eval()
    return model, preprocess, device


def extract_image_features(model, preprocess, image_path, device):
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
        print(f"Error extracting features: {e}")
        return None


def download_and_vectorize(oss_path, model, preprocess, device):
    """从OSS下载图片并提取向量"""
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
        
        if oss_client.download_file(oss_key, tmp_path):
            features = extract_image_features(model, preprocess, tmp_path, device)
            os.unlink(tmp_path)
            return features
        
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return None
    except Exception as e:
        print(f"Error downloading/vectorizing: {e}")
        return None


def get_db_connection():
    """获取数据库连接"""
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME', 'pikachu'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432')
    )
    register_vector(conn)
    return conn


def update_vectors(limit=None, batch_size=100):
    """更新数据库中的image_vector"""
    print("=" * 70)
    print("OSS Image Vectorization Tool")
    print("=" * 70)
    
    if not oss_client.bucket:
        print("ERROR: OSS client not initialized. Check your credentials.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM image_features WHERE image_vector IS NULL")
    null_count = cur.fetchone()[0]
    print(f"Records with NULL image_vector: {null_count}")
    
    cur.execute("SELECT COUNT(*) FROM image_features")
    total_count = cur.fetchone()[0]
    print(f"Total records in database: {total_count}")
    
    model, preprocess, device = init_clip()
    
    sql = """
        SELECT id, image_id, file_path 
        FROM image_features 
        WHERE image_vector IS NULL 
        AND file_path IS NOT NULL 
        AND file_path != ''
    """
    if limit:
        sql += f" LIMIT {limit}"
    
    cur.execute(sql)
    records = cur.fetchall()
    
    if not records:
        print("No records to update.")
        conn.close()
        return
    
    print(f"\nProcessing {len(records)} records...")
    start_time = time.time()
    success_count = 0
    error_count = 0
    skip_count = 0
    
    for idx, (record_id, image_id, file_path) in enumerate(tqdm(records, desc="Processing")):
        try:
            if not file_path or not isinstance(file_path, str):
                skip_count += 1
                continue
            
            if file_path.startswith('http://') or file_path.startswith('https://'):
                skip_count += 1
                continue
            
            features = download_and_vectorize(file_path, model, preprocess, device)
            
            if features is not None:
                cur.execute("""
                    UPDATE image_features 
                    SET image_vector = %s::vector 
                    WHERE id = %s
                """, (features.tolist(), record_id))
                success_count += 1
            else:
                error_count += 1
            
            if (idx + 1) % batch_size == 0:
                conn.commit()
            
        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"\nError processing {image_id}: {e}")
    
    conn.commit()
    
    elapsed = time.time() - start_time
    cur.execute("SELECT COUNT(*) FROM image_features WHERE image_vector IS NOT NULL")
    updated_count = cur.fetchone()[0]
    
    print("\n" + "=" * 70)
    print("Processing Complete!")
    print("=" * 70)
    print(f"Time elapsed: {elapsed/60:.2f} minutes")
    print(f"Processing rate: {success_count/elapsed:.2f} images/second" if elapsed > 0 else "")
    print(f"Successfully updated: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Skipped: {skip_count}")
    print(f"Total with vectors: {updated_count}")
    print("=" * 70)
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Update image vectors from OSS')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of records to process')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for commits')
    args = parser.parse_args()
    
    update_vectors(limit=args.limit, batch_size=args.batch_size)
