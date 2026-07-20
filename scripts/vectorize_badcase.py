#!/usr/bin/env python3
import sys
import os
import psycopg2
from pgvector.psycopg2 import register_vector
from PIL import Image
import torch
import clip
import numpy as np
from tqdm import tqdm

# 数据库配置
DB_CONFIG = {
    'dbname': 'pikachu',
    'user': 'postgres',
    'host': 'localhost',
    'port': '5432'
}

# 数据目录
DATA_DIR = '/Users/pikachu/work/bodeng/yitusoutu/以图搜图_badcase'

def init_clip():
    """初始化CLIP模型"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading CLIP on {device}...")
    model, preprocess = clip.load("ViT-B/32", device=device)
    model.eval()
    return model, preprocess, device

def extract_features(model, preprocess, image_path, device):
    """提取图片特征"""
    try:
        image = Image.open(image_path).convert("RGB")
        image_input = preprocess(image).unsqueeze(0).to(device)
        
        with torch.no_grad():
            features = model.encode_image(image_input)
        
        features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().numpy().flatten()
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None

def main():
    print("=" * 60)
    print("Image Vectorization Tool")
    print("=" * 60)
    
    # 连接数据库
    print("\n1. Connecting to PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)
    cur = conn.cursor()
    print("✅ Connected!")
    
    # 初始化CLIP
    print("\n2. Initializing CLIP model...")
    model, preprocess, device = init_clip()
    print("✅ Model loaded!")
    
    # 获取所有图片
    print("\n3. Scanning images...")
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    images = []
    
    for root, dirs, files in os.walk(DATA_DIR):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                image_path = os.path.join(root, file)
                category = os.path.basename(root)
                images.append({
                    'path': image_path,
                    'category': category,
                    'filename': file,
                    'image_id': os.path.splitext(file)[0]
                })
    
    print(f"Found {len(images)} images")
    
    # 插入向量
    print("\n4. Vectorizing and storing images...")
    for img in tqdm(images, desc="Processing"):
        features = extract_features(model, preprocess, img['path'], device)
        
        if features is not None:
            cur.execute('''
                INSERT INTO image_features 
                (image_id, file_path, file_name, category, image_vector)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (image_id) DO UPDATE SET
                    file_path = EXCLUDED.file_path,
                    file_name = EXCLUDED.file_name,
                    category = EXCLUDED.category,
                    image_vector = EXCLUDED.image_vector
            ''', (img['image_id'], img['path'], img['filename'], img['category'], features.tolist()))
            
            conn.commit()
    
    # 统计
    cur.execute('SELECT COUNT(*) FROM image_features')
    count = cur.fetchone()[0]
    print(f"\n✅ Complete! Total records in database: {count}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
