#!/usr/bin/env python3
"""
测试脚本 - 诊断批量向量化问题
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import torch
import clip
from PIL import Image
import tempfile
import time

print("=" * 60)
print("Test Vectorization Script")
print("=" * 60)

print("\n1. Loading OSS client...")
from src.aliyun_oss import oss_client
print(f"   Bucket: {oss_client.bucket}")
print(f"   Bucket name: {oss_client.bucket_name}")
print(f"   Endpoint: {oss_client.endpoint}")

print("\n2. Initializing CLIP model...")
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"   Using device: {device}")
model, preprocess = clip.load("ViT-B/32", device=device)
model.eval()
print("   CLIP model loaded successfully")

print("\n3. Connecting to database...")
conn = psycopg2.connect(dbname='pikachu', user='postgres', host='localhost', port='5432')
print("   Connected to database")

print("\n4. Getting test records...")
cur = conn.cursor()
cur.execute('''
    SELECT id, image_id, file_path, category, keywords, image_desc 
    FROM image_features 
    WHERE image_vector IS NULL AND file_path LIKE %s
    LIMIT 5
''', ('blink-edge/%',))
records = cur.fetchall()
print(f"   Found {len(records)} test records")

print("\n5. Processing test records...")
for i, (record_id, image_id, file_path, category, keywords, image_desc) in enumerate(records, 1):
    print(f"\n   Record {i}/{len(records)}: {image_id}")
    
    try:
        oss_key = file_path.replace('blink-edge/', '', 1)
        print(f"     OSS key: {oss_key[:50]}...")
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            print("     Downloading from OSS...")
            start = time.time()
            success = oss_client.download_file(oss_key, tmp_path)
            elapsed = time.time() - start
            print(f"     Download completed in {elapsed:.2f}s, success: {success}")
            
            if success:
                print("     Opening image...")
                image = Image.open(tmp_path).convert('RGB')
                
                print("     Processing image...")
                image_input = preprocess(image).unsqueeze(0).to(device)
                
                print("     Extracting image vector...")
                with torch.no_grad():
                    image_vector = model.encode_image(image_input)
                image_vector = image_vector / image_vector.norm(dim=-1, keepdim=True)
                image_vector_np = image_vector.cpu().numpy().flatten()
                print(f"     Image vector shape: {image_vector_np.shape}")
                
                print("     Extracting text vector...")
                combined_text = f'{category}. {keywords}. {image_desc}'.strip()
                if combined_text:
                    text_input = clip.tokenize([combined_text], truncate=True).to(device)
                    with torch.no_grad():
                        text_vector = model.encode_text(text_input)
                    text_vector = text_vector / text_vector.norm(dim=-1, keepdim=True)
                    text_vector_np = text_vector.cpu().numpy().flatten()
                    print(f"     Text vector shape: {text_vector_np.shape}")
                else:
                    text_vector_np = None
                    print("     No text to encode")
                
                print("     Updating database...")
                cur.execute('''
                    UPDATE image_features 
                    SET image_vector = %s::vector, text_vector = %s::vector
                    WHERE image_id = %s
                ''', (image_vector_np.tolist(), text_vector_np.tolist() if text_vector_np is not None else None, image_id))
                conn.commit()
                print("     Database updated successfully")
                
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                print("     Temp file cleaned up")
                
    except Exception as e:
        print(f"     ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("Test completed!")
print("=" * 60)

cur.execute('SELECT COUNT(*) FROM image_features WHERE image_vector IS NOT NULL')
vec_count = cur.fetchone()[0]
print(f"\nRecords with vectors: {vec_count:,}")

conn.close()