#!/usr/bin/env python3
import sys
import os
import psycopg2
from pgvector.psycopg2 import register_vector

def init_database():
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(
        dbname='pikachu',
        user='postgres',
        host='localhost',
        port='5432'
    )
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
    print(f"✅ Database initialized! Current records: {count}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    init_database()
