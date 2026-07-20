import os
import json
from pathlib import Path

def main():
    print("=" * 80)
    print("腾讯云搜图请求文本测试")
    print("=" * 80)
    print()
    
    # 获取所有案例
    data_dir = Path(__file__).parent / '以图搜图_badcase'
    case_dirs = sorted([d for d in os.listdir(data_dir) 
                        if os.path.isdir(os.path.join(data_dir, d))])
    
    for case_name in case_dirs:
        case_path = os.path.join(data_dir, case_name)
        
        # 加载metadata
        metadata_path = os.path.join(case_path, f"{case_name}_metadata.json")
        metadata = {}
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        
        # 构建搜索文本（与style_matcher.py中的逻辑一致）
        style = metadata.get('Style', '')
        
        extra_keywords = []
        if 'Category' in metadata:
            extra_keywords.append(metadata['Category'])
        if 'Keywords' in metadata:
            extra_keywords.append(metadata['Keywords'])
        if 'ImageDescription' in metadata:
            extra_keywords.append(metadata['ImageDescription'])
        
        extra_keywords_str = ' '.join(extra_keywords)
        
        # 最终搜索文本
        search_query = style if style else ''
        if extra_keywords_str:
            search_query = search_query + ' ' + extra_keywords_str if search_query else extra_keywords_str
        if not search_query:
            search_query = '设计 参考图片'
        
        print(f"【案例】{case_name}")
        print(f"  • Style: {style}")
        print(f"  • Category: {metadata.get('Category', 'N/A')}")
        print(f"  • Keywords: {metadata.get('Keywords', 'N/A')}")
        print(f"  • ImageDescription: {metadata.get('ImageDescription', 'N/A')}")
        print()
        print(f"  ✅ 发送给腾讯云的搜索文本:")
        print(f"     {search_query}")
        print()
        print("-" * 80)
        print()

if __name__ == '__main__':
    main()
