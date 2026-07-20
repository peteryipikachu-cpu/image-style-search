#!/usr/bin/env python3
"""
文本向量风格搜索演示
基于风格关键词（如"Claymation"）搜索数据库中相似的图片
"""

import psycopg2
from pgvector.psycopg2 import register_vector
import torch
import clip
import numpy as np

DB_CONFIG = {
    'dbname': 'pikachu',
    'user': 'postgres',
    'host': 'localhost',
    'port': '5432'
}

def search_by_style(style_query, top_k=10):
    """根据风格查询搜索相似的图片"""
    
    # 1. 初始化CLIP并提取查询向量
    print(f"\n🔍 搜索风格: {style_query}")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    
    # 提取查询向量
    text_input = clip.tokenize([style_query], truncate=True).to(device)
    with torch.no_grad():
        query_vector = model.encode_text(text_input)
    query_vector = query_vector / query_vector.norm(dim=-1, keepdim=True)
    query_list = query_vector.cpu().numpy().flatten().tolist()
    
    # 2. 连接数据库并搜索
    conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)
    cur = conn.cursor()
    
    # 3. 执行向量搜索
    cur.execute('''
        SELECT 
            image_id, 
            category, 
            keywords,
            image_desc,
            1 - (text_vector <=> %s::vector) AS similarity
        FROM image_features
        WHERE text_vector IS NOT NULL
        ORDER BY text_vector <=> %s::vector
        LIMIT %s
    ''', (query_list, query_list, top_k))
    
    results = cur.fetchall()
    
    # 4. 显示结果
    print(f"\n📊 找到 {len(results)} 条相似结果:\n")
    print("排名 | 类别 | 相似度 | 关键词")
    print("-" * 80)
    
    for i, (image_id, category, keywords, image_desc, similarity) in enumerate(results, 1):
        sim_pct = similarity * 100
        kw = keywords[:50] if keywords else '无'
        print(f"{i:2d}   | {category:8s} | {sim_pct:5.1f}% | {kw}...")
    
    cur.close()
    conn.close()
    
    return results

def main():
    print("=" * 80)
    print("文本向量风格搜索演示")
    print("基于CLIP模型和PostgreSQL向量搜索")
    print("=" * 80)
    
    # 测试几个风格查询
    queries = [
        "Claymation",
        "Oil painting",
        "Watercolor",
        "3D render",
        "Cartoon"
    ]
    
    for query in queries:
        search_by_style(query, top_k=5)
    
    print("\n" + "=" * 80)
    print("✅ 演示完成！")
    print("\n您可以:")
    print("1. 修改上面的queries列表测试其他风格")
    print("2. 将这个搜索逻辑集成到系统中")
    print("3. 运行 scripts/quick_vectorize.py 处理更多数据")
    print("=" * 80)

if __name__ == "__main__":
    main()
