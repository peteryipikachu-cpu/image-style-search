#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, '/Users/pikachu/work/bodeng/yitusoutu')

from src.style_matcher import StyleMatcher

# 配置
DATA_DIR = '/Users/pikachu/work/bodeng/yitusoutu/以图搜图_badcase'
DB_CONFIG = {
    'dbname': 'pikachu',
    'user': 'postgres',
    'password': '',
    'host': 'localhost',
    'port': '5432'
}

print("=" * 60)
print("Testing StyleMatcher with PostgreSQL Database")
print("=" * 60)

# 初始化
print("\n1. Initializing StyleMatcher...")
matcher = StyleMatcher(
    parquet_file=None,
    data_dir=DATA_DIR,
    db_config=DB_CONFIG,
    use_db=True
)
print(f"✅ Matcher initialized")
print(f"   - use_db: {matcher.use_db}")
print(f"   - db: {matcher.db}")
print(f"   - cached_images: {len(matcher.cached_images)}")

# 测试分析单个case
print("\n2. Testing analyze_badcase for case_001...")
case_path = os.path.join(DATA_DIR, 'case_001')
result = matcher.analyze_badcase(case_path)

print(f"\n✅ Analysis result:")
print(f"   Case: {result.get('case_name')}")
print(f"   Style: {result.get('style')}")
print(f"   Similarities: {len(result.get('similarities', {}))} items")
print(f"   Suggested references: {len(result.get('suggested_references', []))} items")

if result.get('suggested_references'):
    print(f"\n   Top 3 suggestions:")
    for i, ref in enumerate(result.get('suggested_references')[:3], 1):
        print(f"   {i}. {ref.get('file_name')}")
        print(f"      - Combined Score: {ref.get('combined_score', 0):.2%}")
        print(f"      - Content Sim: {ref.get('content_similarity', 0):.2%}")
        print(f"      - Style Sim: {ref.get('style_similarity', 0):.2%}")
else:
    print(f"\n⚠️ No suggested references found!")
    print(f"   Database may not be properly queried")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
