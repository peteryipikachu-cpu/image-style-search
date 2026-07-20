#!/usr/bin/env python3
"""
批量提取向量脚本 - 调试版
逐条处理记录并打印详细信息
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
import socket
import traceback

socket.setdefaulttimeout(15)

def log(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()

def init_clip():
    log("Initializing CLIP model...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log(f"Using device: {device}")
    model, preprocess = clip.load("ViT-B/32", device=device)
    model.eval()
    log("CLIP model loaded successfully")
    return model, preprocess, device

def get_pending_count(conn):
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM image_features WHERE image_vector IS NULL AND file_path LIKE %s', ('blink-edge/%',))
    return cur.fetchone()[0]

def get_batch(conn, limit=100):
    cur = conn.cursor()
    cur.execute('''
        SELECT id, image_id, file_path, category, keywords, image_desc 
        FROM image_features 
        WHERE image_vector IS NULL AND file_path LIKE %s
        LIMIT %s
    ''', ('blink-edge/%', limit))
    return cur.fetchall()

def main():
    log("=" * 70)
    log("Batch Vectorization Script - Debug Version")
    log("=" * 70)
    
    log("\n1. Loading OSS client...")
    from src.aliyun_oss import oss_client
    
    if not oss_client.bucket:
        log("ERROR: OSS client not initialized!")
        return
    
    log(f"  Bucket: {oss_client.bucket_name}")
    log(f"  Endpoint: {oss_client.endpoint}")
    log("  OSS client initialized successfully")
    
    log("\n2. Initializing CLIP model...")
    model, preprocess, device = init_clip()
    log(f"  CLIP model loaded on {device}")
    
    log("\n3. Connecting to database...")
    conn = psycopg2.connect(dbname='pikachu', user='postgres', host='localhost', port='5432')
    log("  Connected to database")
    
    pending = get_pending_count(conn)
    log(f"\n4. Pending records to vectorize: {pending:,}")
    
    if pending == 0:
        log("All records already have vectors!")
        conn.close()
        return
    
    total_success = 0
    total_error = 0
    batch_num = 0
    start_time = time.time()
    
    log("\n5. Starting batch processing...")
    log("-" * 70)
    
    while True:
        batch_num += 1
        
        records = get_batch(conn, 100)
        
        if not records:
            log("No more records to process")
            break
        
        log(f"\nBatch {batch_num}: Processing {len(records)} records...")
        
        updates = []
        success = 0
        error = 0
        
        for idx, record in enumerate(records, 1):
            record_id, image_id, file_path, category, keywords, image_desc = record
            log(f"  [{idx}/{len(records)}] Processing {image_id[:12]}...")
            
            try:
                oss_key = file_path.replace('blink-edge/', '', 1)
                log(f"    Downloading {oss_key[:40]}...")
                
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    tmp_path = tmp.name
                
                try:
                    if oss_client.download_file(oss_key, tmp_path):
                        log("    Opening image...")
                        image = Image.open(tmp_path).convert('RGB')
                        
                        log("    Processing image...")
                        image_input = preprocess(image).unsqueeze(0).to(device)
                        
                        log("    Extracting image vector...")
                        with torch.no_grad():
                            image_vector = model.encode_image(image_input)
                        image_vector = image_vector / image_vector.norm(dim=-1, keepdim=True)
                        image_vector_np = image_vector.cpu().numpy().flatten()
                        
                        log("    Extracting text vector...")
                        combined_text = f'{category}. {keywords}. {image_desc}'.strip()
                        if combined_text:
                            text_input = clip.tokenize([combined_text], truncate=True).to(device)
                            with torch.no_grad():
                                text_vector = model.encode_text(text_input)
                            text_vector = text_vector / text_vector.norm(dim=-1, keepdim=True)
                            text_vector_np = text_vector.cpu().numpy().flatten()
                        else:
                            text_vector_np = None
                        
                        updates.append((image_vector_np.tolist(), text_vector_np.tolist() if text_vector_np is not None else None, image_id))
                        success += 1
                        log("    OK")
                    else:
                        error += 1
                        log("    FAILED: Download failed")
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                        
            except Exception as e:
                error += 1
                log(f"    ERROR: {str(e)[:50]}")
        
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
                    log(f"  DB update error for {img_id[:12]}: {str(e)[:30]}")
            conn.commit()
            log(f"  Committed {len(updates)} updates")
        
        total_success += success
        total_error += error
        
        elapsed = time.time() - start_time
        rate = total_success / elapsed if elapsed > 0 else 0
        remaining = (pending - total_success) / rate if rate > 0 else 0
        
        log(f"  Batch {batch_num} completed: {success} success, {error} error")
        log(f"  Total: {total_success:,} success, {total_error:,} error")
        log(f"  Progress: {total_success}/{pending} ({total_success/pending*100:.1f}%)")
        log(f"  Rate: {rate:.2f} img/s, ETA: {remaining/3600:.1f} hours")
        
        sys.stdout.flush()
    
    elapsed = time.time() - start_time
    log("\n" + "=" * 70)
    log("Processing Complete!")
    log("=" * 70)
    log(f"Total records processed: {total_success + total_error:,}")
    log(f"Success: {total_success:,}")
    log(f"Errors: {total_error:,}")
    log(f"Time elapsed: {elapsed/60:.2f} minutes")
    log(f"Average rate: {total_success/elapsed:.2f} images/second")
    
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM image_features WHERE image_vector IS NOT NULL')
    vec_count = cur.fetchone()[0]
    log(f"\nRecords with vectors in database: {vec_count:,}")
    
    conn.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"Fatal error: {str(e)}")
        traceback.print_exc()