#!/usr/bin/env python3
"""
批量提取向量脚本 - 优化版
使用多线程并行处理，大幅提升处理速度
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

def init_clip():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading CLIP model on {device}...")
    model, preprocess = clip.load("ViT-B/32", device=device)
    model.eval()
    return model, preprocess, device

def get_pending_count(conn):
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM image_features WHERE image_vector IS NULL AND file_path LIKE %s', ('blink-edge/%',))
    return cur.fetchone()[0]

def get_batch(conn, limit=500):
    cur = conn.cursor()
    cur.execute('''
        SELECT id, image_id, file_path, category, keywords, image_desc 
        FROM image_features 
        WHERE image_vector IS NULL AND file_path LIKE %s
        LIMIT %s
    ''', ('blink-edge/%', limit))
    return cur.fetchall()

def process_record(record, model, preprocess, device, oss_client):
    record_id, image_id, file_path, category, keywords, image_desc = record
    try:
        oss_key = file_path.replace('blink-edge/', '', 1)
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            if oss_client.download_file(oss_key, tmp_path):
                image = Image.open(tmp_path).convert('RGB')
                image_input = preprocess(image).unsqueeze(0).to(device)
                
                with torch.no_grad():
                    image_vector = model.encode_image(image_input)
                image_vector = image_vector / image_vector.norm(dim=-1, keepdim=True)
                image_vector_np = image_vector.cpu().numpy().flatten()
                
                combined_text = f'{category}. {keywords}. {image_desc}'.strip()
                if combined_text:
                    text_input = clip.tokenize([combined_text], truncate=True).to(device)
                    with torch.no_grad():
                        text_vector = model.encode_text(text_input)
                    text_vector = text_vector / text_vector.norm(dim=-1, keepdim=True)
                    text_vector_np = text_vector.cpu().numpy().flatten()
                else:
                    text_vector_np = None
                
                return (image_id, image_vector_np.tolist(), text_vector_np.tolist() if text_vector_np is not None else None)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        return (image_id, None, str(e)[:50])

def main():
    from src.aliyun_oss import oss_client
    
    print("=" * 70)
    print("Batch Vectorization Script - Optimized Version")
    print("=" * 70)
    
    if not oss_client.bucket:
        print("ERROR: OSS client not initialized!")
        return
    
    print("\nInitializing CLIP model...")
    model, preprocess, device = init_clip()
    print(f"CLIP model loaded on {device}")
    
    print("\nConnecting to database...")
    conn = psycopg2.connect(dbname='pikachu', user='postgres', host='localhost', port='5432')
    print("Connected to database")
    
    pending = get_pending_count(conn)
    print(f"\nPending records to vectorize: {pending:,}")
    
    if pending == 0:
        print("All records already have vectors!")
        conn.close()
        return
    
    total_success = 0
    total_error = 0
    batch_num = 0
    start_time = time.time()
    
    num_workers = 8
    batch_size = 200
    
    print(f"\nStarting batch processing with {num_workers} threads...")
    print("-" * 70)
    
    while True:
        batch_num += 1
        
        records = get_batch(conn, batch_size)
        
        if not records:
            break
        
        print(f"\nBatch {batch_num}: Processing {len(records)} records...")
        
        updates = []
        success = 0
        error = 0
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(process_record, record, model, preprocess, device, oss_client): record for record in records}
            
            for future in as_completed(futures):
                result = future.result()
                image_id, image_vector, text_or_error = result
                
                if image_vector is not None:
                    updates.append((image_vector, text_or_error, image_id))
                    success += 1
                else:
                    error += 1
                    print(f"  Error processing {image_id}: {text_or_error}")
        
        if updates:
            cur = conn.cursor()
            for image_vector, text_vector, img_id in updates:
                try:
                    cur.execute('''
                        UPDATE image_features 
                        SET image_vector = %s::vector, text_vector = %s::vector
                        WHERE image_id = %s
                    ''', (image_vector, text_vector, img_id))
                except Exception as e:
                    pass
            conn.commit()
        
        total_success += success
        total_error += error
        
        elapsed = time.time() - start_time
        rate = total_success / elapsed if elapsed > 0 else 0
        remaining = (pending - total_success) / rate if rate > 0 else 0
        
        print(f"  Batch {batch_num} completed: {success} success, {error} error")
        print(f"  Total: {total_success:,} success, {total_error:,} error")
        print(f"  Progress: {total_success}/{pending} ({total_success/pending*100:.1f}%)")
        print(f"  Rate: {rate:.2f} img/s, ETA: {remaining/3600:.1f} hours")
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("Processing Complete!")
    print("=" * 70)
    print(f"Total records processed: {total_success + total_error:,}")
    print(f"Success: {total_success:,}")
    print(f"Errors: {total_error:,}")
    print(f"Time elapsed: {elapsed/60:.2f} minutes")
    print(f"Average rate: {total_success/elapsed:.2f} images/second")
    
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM image_features WHERE image_vector IS NOT NULL')
    vec_count = cur.fetchone()[0]
    print(f"\nRecords with vectors in database: {vec_count:,}")
    
    conn.close()

if __name__ == "__main__":
    main()