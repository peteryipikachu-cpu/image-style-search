import os
import sqlite3
import numpy as np
from contextlib import contextmanager

class VectorDatabase:
    def __init__(self, db_path='vectors.db'):
        self.db_path = db_path
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS image_features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id TEXT UNIQUE NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT,
                    category TEXT,
                    image_desc TEXT,
                    keywords TEXT,
                    image_vector BLOB,
                    text_vector BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_image_id ON image_features(image_id)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_category ON image_features(category)')
            conn.commit()
    
    def insert_image_feature(self, image_id, file_path, file_name, category, 
                           image_desc, keywords, image_vector, text_vector):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO image_features 
                (image_id, file_path, file_name, category, image_desc, keywords, image_vector, text_vector)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (image_id, file_path, file_name, category, image_desc, keywords, 
                 image_vector.tobytes() if image_vector is not None else None,
                 text_vector.tobytes() if text_vector is not None else None))
            conn.commit()
    
    def _cosine_similarity(self, vec1, vec2):
        if vec1 is None or vec2 is None:
            return 0.0
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return np.dot(vec1, vec2) / (norm1 * norm2)
    
    def search_by_vector(self, query_vector, top_k=10, alpha=0.5):
        """
        使用向量搜索图片
        
        Args:
            query_vector: 查询向量
            top_k: 返回数量
            alpha: 图片向量权重 (0-1)
            
        Returns:
            按相似度排序的结果列表
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM image_features')
            results = []
            for row in cur.fetchall():
                image_vec = np.frombuffer(row['image_vector'], dtype=np.float32) if row['image_vector'] else None
                text_vec = np.frombuffer(row['text_vector'], dtype=np.float32) if row['text_vector'] else None
                
                if image_vec is not None:
                    image_sim = self._cosine_similarity(query_vector, image_vec)
                else:
                    image_sim = 0.0
                
                if text_vec is not None:
                    text_sim = self._cosine_similarity(query_vector, text_vec)
                else:
                    text_sim = 0.0
                
                combined_score = alpha * image_sim + (1 - alpha) * text_sim
                
                results.append({
                    'id': row['id'],
                    'image_id': row['image_id'],
                    'file_path': row['file_path'],
                    'file_name': row['file_name'],
                    'category': row['category'],
                    'image_desc': row['image_desc'],
                    'keywords': row['keywords'],
                    'image_similarity': float(image_sim),
                    'text_similarity': float(text_sim),
                    'combined_score': float(combined_score)
                })
            
            results.sort(key=lambda x: x['combined_score'], reverse=True)
            return results[:top_k]
    
    def search_by_text_features(self, text_features, top_k=10, alpha=0.5):
        """
        使用文本特征向量搜索图片
        
        Args:
            text_features: 文本特征向量 (numpy array)
            top_k: 返回数量
            alpha: 图片向量权重 (0-1)，这里主要用于与图片向量的比较
            
        Returns:
            按相似度排序的结果列表
        """
        print(f"Using CLIP text features for vector search (shape: {text_features.shape})")
        return self.search_by_vector(text_features, top_k=top_k, alpha=alpha)
    
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
            cur = conn.cursor()
            pattern = f'%{style}%'
            
            cur.execute('''
                SELECT * FROM image_features 
                WHERE keywords LIKE ? OR image_desc LIKE ?
                ORDER BY 
                    CASE 
                        WHEN keywords LIKE ? THEN 2
                        WHEN image_desc LIKE ? THEN 1
                        ELSE 0
                    END DESC
            ''', (pattern, pattern, pattern, pattern))
            
            results = []
            for row in cur.fetchall():
                keywords_match = style.lower() in (row['keywords'] or '').lower()
                desc_match = style.lower() in (row['image_desc'] or '').lower()
                
                if keywords_match:
                    match_score = 0.8 + (0.2 if desc_match else 0)
                elif desc_match:
                    match_score = 0.6
                else:
                    match_score = 0.0
                
                results.append({
                    'id': row['id'],
                    'image_id': row['image_id'],
                    'file_path': row['file_path'],
                    'file_name': row['file_name'],
                    'category': row['category'],
                    'image_desc': row['image_desc'],
                    'keywords': row['keywords'],
                    'combined_score': float(match_score),
                    'match_type': 'keywords' if keywords_match else 'description'
                })
            
            results.sort(key=lambda x: x['combined_score'], reverse=True)
            return results[:top_k]
    
    def get_count(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM image_features')
            count = cur.fetchone()[0]
            return count
    
    def clear_all(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('DELETE FROM image_features')
            conn.commit()
