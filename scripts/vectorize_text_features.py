#!/usr/bin/env python3
"""
Parquet图片文本特征向量化脚本
由于没有本地图片，我们先基于元数据（category + keywords + image_desc）提取文本特征向量
存入数据库后可以直接进行风格匹配搜索
"""

import sys
import os
import psycopg2
from pgvector.psycopg2 import register_vector
import pandas as pd
import torch
import clip
import numpy as np
from tqdm import tqdm
import time

# 配置
PARQUET_FILE = '/Users/pikachu/work/bodeng/yitusoutu/ps_image_9138446_part00.parquet'
BATCH_SIZE = 100
LIMIT = 1000  # 先测试1000条

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
        print(f"Error extracting text features: {e}")
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
    cur.execute('CREATE INDEX IF NOT EXISTS idx_image_vector ON image_features USING ivfflat (image_vector vector_cosine_ops)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_text_vector ON image_features USING ivfflat (text_vector vector_cosine_ops)')
    
    conn.commit()
    
    cur.execute('SELECT COUNT(*) FROM image_features')
    count = cur.fetchone()[0]
    print(f"Current records in database: {count}")
    
    return conn, cur

def main():
    print("=" * 70)
    print("Image Text Vectorization Tool")
    print("基于category + keywords + image_desc提取文本特征向量")
    print("=" * 70)
    
    # 连接数据库
    conn, cur = init_database()
    
    # 初始化CLIP
    print("\nInitializing CLIP model...")
    model, preprocess, device = init_clip()
    
    # 读取parquet
    print(f"\nLoading parquet file: {PARQUET_FILE}")
    df = pd.read_parquet(PARQUET_FILE)
    
    if LIMIT:
        df = df.head(LIMIT)
        print(f"Processing limited to {LIMIT} records")
    
    print(f"Total records to process: {len(df)}")
    
    # 处理记录
    success_count = 0
    error_count = 0
    
    print("\nProcessing text features...")
    start_time = time.time()
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Vectorizing"):
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
            
            # 构建文本特征
            combined_text = f"{category}. {keywords}. {image_desc}".strip()
            text_vector = extract_text_features(model, combined_text, device)
            
            if text_vector is None:
                error_count += 1
                continue
            
            # 插入数据库
            cur.execute('''
                INSERT INTO image_features 
                (image_id, file_path, file_name, category, image_desc, keywords, 
                 image_phash, origin_category, project_flag, text_vector)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (image_id) DO UPDATE SET
                    file_path = EXCLUDED.file_path,
                    file_name = EXCLUDED.file_name,
                    category = EXCLUDED.category,
                    image_desc = EXCLUDED.image_desc,
                    keywords = EXCLUDED.keywords,
                    text_vector = EXCLUDED.text_vector
            ''', (image_id, file_path, file_name, category, image_desc, keywords,
                 image_phash, origin_category, project_flag, text_vector.tolist()))
            
            # 每1000条提交一次
            if (success_count + 1) % 1000 == 0:
                conn.commit()
                elapsed = time.time() - start_time
                rate = (success_count + 1) / elapsed
                remaining = (len(df) - success_count - 1) / rate if rate > 0 else 0
                print(f"\n  Progress: {success_count + 1}/{len(df)} "
                      f"({(success_count + 1) / len(df) * 100:.1f}%) "
                      f"- Rate: {rate:.1f} text/s - ETA: {remaining/60:.1f} min")
            
            success_count += 1
            
        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"\nError processing {row.get('image_id', 'unknown')}: {e}")
    
    # 最终提交
    conn.commit()
    
    # 统计
    elapsed = time.time() - start_time
    cur.execute('SELECT COUNT(*) FROM image_features')
    total_count = cur.fetchone()[0]
    
    print("\n" + "=" * 70)
    print("Processing Complete!")
    print("=" * 70)
    print(f"Time elapsed: {elapsed/60:.2f} minutes")
    print(f"Processing rate: {success_count/elapsed:.2f} texts/second")
    print(f"Successfully processed: {success_count}")
    print(f"Errors/Skipped: {error_count}")
    print(f"Total in database: {total_count}")
    print("=" * 70)
    print("\n下一步:")
    print("1. 如果有图片URL或可访问的图片，可以继续提取图片特征")
    print("2. 修改搜索算法使用文本特征向量进行匹配")
    print("3. 可以通过 /api/search_text 接口搜索相似风格的图片")
    print("=" * 70)
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
