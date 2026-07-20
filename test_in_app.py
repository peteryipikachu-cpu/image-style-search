#!/usr/bin/env python3
"""Test Tencent API integration in the app environment"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tencent_image_search import TencentImageSearch

SECRET_ID = os.getenv('TENCENT_SECRET_ID')
SECRET_KEY = os.getenv('TENCENT_SECRET_KEY')

if not SECRET_ID or not SECRET_KEY:
    print("Missing TENCENT_SECRET_ID or TENCENT_SECRET_KEY; skipping Tencent API integration test.")
    sys.exit(0)

print("Testing Tencent Cloud Image Search API integration...")
print("=" * 60)

try:
    search = TencentImageSearch(SECRET_ID, SECRET_KEY)
    
    # Test 1: Simple text search
    print("\nTest 1: Search by text - '故宫'")
    results = search.search_image_by_text('故宫', limit=2)
    print(f"Found {len(results)} results:")
    for i, res in enumerate(results):
        print(f"  {i+1}. {res['title']}")
        print(f"     Thumbnail: {res['thumbnail_url'][:80]}...")
    
    # Test 2: Style-based search
    print("\nTest 2: Search by style - '新中式 插画'")
    results = search.search_image_by_image(None, '新中式 插画')
    print(f"Found {len(results)} results:")
    for i, res in enumerate(results):
        print(f"  {i+1}. {res['title']}")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
