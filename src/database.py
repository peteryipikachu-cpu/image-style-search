import os
import sys
import psycopg2
from pgvector.psycopg2 import register_vector
import numpy as np
from contextlib import contextmanager

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

class Database:
    def __init__(self, db_config=None):
        self.config = db_config or {
            'dbname': os.getenv('DB_NAME', 'image_search'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', ''),
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432')
        }
    
    @contextmanager
    def get_connection(self):
        conn = psycopg2.connect(**self.config)
        register_vector(conn)
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS image_features (
                        id SERIAL PRIMARY KEY,
                        image_id VARCHAR(255) UNIQUE NOT NULL,
                        file_path TEXT NOT NULL,
                        file_name VARCHAR(255),
                        category VARCHAR(255),
                        image_desc TEXT,
                        keywords TEXT,
                        image_vector vector(512),
                        text_vector vector(512),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cur.execute('CREATE INDEX IF NOT EXISTS idx_image_id ON image_features(image_id)')
                cur.execute('CREATE INDEX IF NOT EXISTS idx_category ON image_features(category)')
                cur.execute('CREATE INDEX IF NOT EXISTS idx_image_vector ON image_features USING ivfflat (image_vector vector_cosine_ops)')
                cur.execute('CREATE INDEX IF NOT EXISTS idx_text_vector ON image_features USING ivfflat (text_vector vector_cosine_ops)')
            conn.commit()
    
    def insert_image_feature(self, image_id, file_path, file_name, category, 
                           image_desc, keywords, image_vector, text_vector):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO image_features 
                    (image_id, file_path, file_name, category, image_desc, keywords, image_vector, text_vector)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (image_id) DO UPDATE SET
                        file_path = EXCLUDED.file_path,
                        file_name = EXCLUDED.file_name,
                        category = EXCLUDED.category,
                        image_desc = EXCLUDED.image_desc,
                        keywords = EXCLUDED.keywords,
                        image_vector = EXCLUDED.image_vector,
                        text_vector = EXCLUDED.text_vector
                ''', (image_id, file_path, file_name, category, image_desc, keywords, 
                     image_vector.tolist() if image_vector is not None else None,
                     text_vector.tolist() if text_vector is not None else None))
            conn.commit()
    
    def search_by_image_vector(self, query_vector, top_k=10, alpha=0.5):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                vec_list = query_vector.tolist()
                cur.execute('''
                    SELECT 
                        id, image_id, file_path, file_name, category, 
                        image_desc, keywords,
                        1 - (image_vector <=> %s::vector) AS image_similarity,
                        1 - (COALESCE(text_vector, image_vector) <=> %s::vector) AS text_similarity,
                        (1 - (image_vector <=> %s::vector)) * %s + (1 - (COALESCE(text_vector, image_vector) <=> %s::vector)) * (1 - %s) AS combined_score
                    FROM image_features
                    WHERE image_vector IS NOT NULL
                    ORDER BY combined_score DESC
                    LIMIT %s
                ''', (vec_list, vec_list, vec_list, alpha, vec_list, alpha, top_k))
                results = []
                for row in cur.fetchall():
                    results.append({
                        'id': row[0],
                        'image_id': row[1],
                        'file_path': row[2],
                        'file_name': row[3],
                        'category': row[4],
                        'image_desc': row[5],
                        'keywords': row[6],
                        'image_similarity': float(row[7]) if row[7] is not None else 0.0,
                        'text_similarity': float(row[8]) if row[8] is not None else 0.0,
                        'combined_score': float(row[9]) if row[9] is not None else 0.0
                    })
                return results
    
    def search_by_text_vector(self, query_vector, top_k=10, alpha=0.5):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                vec_list = query_vector.tolist()
                cur.execute('''
                    SELECT 
                        id, image_id, file_path, file_name, category, 
                        image_desc, keywords,
                        1 - (image_vector <=> %s::vector) AS image_similarity,
                        1 - (COALESCE(text_vector, image_vector) <=> %s::vector) AS text_similarity,
                        (1 - (image_vector <=> %s::vector)) * (1 - %s) + (1 - (COALESCE(text_vector, image_vector) <=> %s::vector)) * %s AS combined_score
                    FROM image_features
                    ORDER BY combined_score DESC
                    LIMIT %s
                ''', (vec_list, vec_list, vec_list, alpha, vec_list, alpha, top_k))
                results = []
                for row in cur.fetchall():
                    results.append({
                        'id': row[0],
                        'image_id': row[1],
                        'file_path': row[2],
                        'file_name': row[3],
                        'category': row[4],
                        'image_desc': row[5],
                        'keywords': row[6],
                        'image_similarity': float(row[7]) if row[7] is not None else 0.0,
                        'text_similarity': float(row[8]) if row[8] is not None else 0.0,
                        'combined_score': float(row[9]) if row[9] is not None else 0.0
                    })
                return results
    
    def search_by_keywords(self, style, top_k=10):
        """
        使用关键词在keywords和image_desc字段中进行文本搜索
        
        Args:
            style: 搜索关键词（风格词）
            top_k: 返回数量
            
        Returns:
            匹配的参考图列表
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                pattern = f'%{style}%'
                
                cur.execute('''
                    SELECT 
                        id, image_id, file_path, file_name, category, 
                        image_desc, keywords
                    FROM image_features 
                    WHERE keywords ILIKE %s OR image_desc ILIKE %s
                    ORDER BY 
                        CASE 
                            WHEN keywords ILIKE %s THEN 2
                            WHEN image_desc ILIKE %s THEN 1
                            ELSE 0
                        END DESC
                    LIMIT %s
                ''', (pattern, pattern, pattern, pattern, top_k))
                
                results = []
                for row in cur.fetchall():
                    keywords = row[6] or ''
                    desc = row[5] or ''
                    
                    keywords_match = style.lower() in keywords.lower()
                    desc_match = style.lower() in desc.lower()
                    
                    if keywords_match:
                        match_score = 0.8 + (0.2 if desc_match else 0)
                    elif desc_match:
                        match_score = 0.6
                    else:
                        match_score = 0.0
                    
                    results.append({
                        'id': row[0],
                        'image_id': row[1],
                        'file_path': row[2],
                        'file_name': row[3],
                        'category': row[4],
                        'image_desc': row[5],
                        'keywords': row[6],
                        'combined_score': float(match_score),
                        'match_type': 'keywords' if keywords_match else 'description'
                    })
                
                return results
    
    def get_count(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM image_features')
                return cur.fetchone()[0]
    
    def get_vector_stats(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN image_vector IS NOT NULL THEN 1 END) as with_image_vector,
                        COUNT(CASE WHEN text_vector IS NOT NULL THEN 1 END) as with_text_vector
                    FROM image_features
                ''')
                row = cur.fetchone()
                return {
                    'total': row[0],
                    'with_image_vector': row[1],
                    'with_text_vector': row[2]
                }
