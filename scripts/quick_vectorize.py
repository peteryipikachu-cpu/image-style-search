#!/usr/bin/env python3
"""
Parquet图片文本特征向量化脚本 - 简化版
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

# 配置
PARQUET_FILE = '/Users/pikachu/work/bodeng/yitusoutu/ps_image_9138446_part00.parquet'
LIMIT = 1000  # 先处理1000条测试

DB_CONFIG = {
    'dbname': 'pikachu',
    'user': 'postgres',
    'host': 'localhost',
    'port': '5432'
}

print("=" * 70)
print("开始文本特征向量化")
print("=" * 70)

# 1. 连接数据库
print("\n[1/4] 连接数据库...")
conn = psycopg2.connect(**DB_CONFIG)
register_vector(conn)
cur = conn.cursor()
print("✅ 数据库连接成功")

# 2. 初始化CLIP
print("\n[2/4] 加载CLIP模型...")
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"   使用设备: {device}")
model, preprocess = clip.load("ViT-B/32", device=device)
print("✅ CLIP模型加载成功")

# 3. 读取parquet
print(f"\n[3/4] 读取parquet文件 (限制{LIMIT}条)...")
df = pd.read_parquet(PARQUET_FILE)
df = df.head(LIMIT)
print(f"✅ 读取成功: {len(df)} 条记录")

# 4. 处理数据
print("\n[4/4] 开始处理...")
success = 0
errors = 0

for idx, row in tqdm(df.iterrows(), total=len(df), desc="处理中"):
    try:
        image_id = row['image_id']
        file_path = row['file_path']
        category = row.get('category', '')
        keywords = row.get('keywords', '')
        image_desc = row.get('image_desc', '')
        
        # 构建文本
        combined_text = f"{category}. {keywords}. {image_desc}".strip()
        
        if not combined_text:
            errors += 1
            continue
        
        # 提取特征
        text_input = clip.tokenize([combined_text], truncate=True).to(device)
        with torch.no_grad():
            features = model.encode_text(text_input)
        features = features / features.norm(dim=-1, keepdim=True)
        vector = features.cpu().numpy().flatten().tolist()
        
        # 插入数据库
        cur.execute('''
            INSERT INTO image_features 
            (image_id, file_path, category, keywords, image_desc, text_vector)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (image_id) DO UPDATE SET
                text_vector = EXCLUDED.text_vector,
                category = EXCLUDED.category,
                keywords = EXCLUDED.keywords,
                image_desc = EXCLUDED.image_desc
        ''', (image_id, file_path, category, keywords, image_desc, vector))
        
        success += 1
        
        # 每100条提交一次
        if success % 100 == 0:
            conn.commit()
            print(f"   已处理: {success} 条")
        
    except Exception as e:
        errors += 1
        if errors <= 3:
            print(f"   错误: {e}")

# 最终提交
conn.commit()

# 统计
cur.execute('SELECT COUNT(*) FROM image_features WHERE text_vector IS NOT NULL')
count = cur.fetchone()[0]

print("\n" + "=" * 70)
print("处理完成!")
print("=" * 70)
print(f"成功处理: {success} 条")
print(f"失败/跳过: {errors} 条")
print(f"数据库中带向量的记录: {count} 条")
print("=" * 70)

cur.close()
conn.close()
