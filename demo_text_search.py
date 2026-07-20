#!/usr/bin/env python3
"""
演示CLIP文本到图像搜索
"""
import os
import sys
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.feature_extractor import FeatureExtractor
from src.vector_db import VectorDatabase

def text_to_image_search(query_text: str, top_k: int = 5):
    """
    使用文本搜索图片
    
    Args:
        query_text: 查询文本
        top_k: 返回前k个结果
    """
    print(f"\n🔍 文搜图: '{query_text}'")
    print("=" * 60)
    
    # 初始化CLIP特征提取器
    extractor = FeatureExtractor()
    
    # 1. 提取文本特征
    text_features = extractor.extract_text_features(query_text)
    if text_features is None:
        print("❌ 文本特征提取失败")
        return
    
    print(f"✅ 文本特征向量形状: {text_features.shape}")
    
    # 2. 获取所有本地图片
    # 遍历badcase目录收集所有图片
    from config import Config
    
    all_images = []
    for root, dirs, files in os.walk(Config.DATA_DIR):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                all_images.append(os.path.join(root, file))
    
    print(f"📸 找到 {len(all_images)} 张图片")
    
    # 3. 提取所有图片特征并计算相似度
    results = []
    for img_path in all_images:
        img_features = extractor.extract_image_features(img_path)
        if img_features is not None:
            # 计算余弦相似度
            similarity = cosine_similarity([text_features], [img_features])[0][0]
            results.append((img_path, similarity))
    
    # 4. 按相似度排序
    results.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n📊 搜索结果 (Top {top_k}):")
    print("-" * 60)
    
    for idx, (img_path, sim) in enumerate(results[:top_k], 1):
        filename = os.path.basename(img_path)
        print(f"{idx}. {filename}")
        print(f"   相似度: {sim:.4f} ({sim*100:.1f}%)")
        print(f"   路径: {img_path}")
        print()

if __name__ == "__main__":
    # 测试不同的查询
    queries = [
        "一只可爱的猫",
        "复古风格摄影",
        "电影感画面",
        "粘土动画风格",
        "抽象艺术"
    ]
    
    for query in queries:
        text_to_image_search(query, top_k=3)
        print("\n" + "="*80 + "\n")
