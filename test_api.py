#!/usr/bin/env python3
"""
系统测试脚本
测试所有API端点和功能
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5001"

def test_cases_api():
    """测试案例列表API"""
    print("\n📋 Testing /api/cases...")
    try:
        resp = requests.get(f"{BASE_URL}/api/cases", timeout=5)
        resp.raise_for_status()
        cases = resp.json()
        print(f"✅ Found {len(cases)} cases: {cases}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_analyze_all():
    """测试分析所有案例"""
    print("\n🔍 Testing /api/analyze (all cases)...")
    try:
        resp = requests.get(f"{BASE_URL}/api/analyze", timeout=30)
        resp.raise_for_status()
        results = resp.json()
        print(f"✅ Analyzed {len(results)} cases")
        return results
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_analyze_case(case_name):
    """测试分析单个案例"""
    print(f"\n🎯 Testing /api/analyze/{case_name}...")
    try:
        resp = requests.get(f"{BASE_URL}/api/analyze/{case_name}", timeout=30)
        resp.raise_for_status()
        result = resp.json()
        
        if 'error' in result:
            print(f"❌ Error in response: {result['error']}")
            return False
        
        print(f"✅ Case: {result.get('case_name')}")
        print(f"   Style: {result.get('style')}")
        print(f"   Similarities: {len(result.get('similarities', {}))}")
        print(f"   Suggested: {len(result.get('suggested_references', []))} references")
        
        return result
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_web_interface():
    """测试Web界面"""
    print("\n🌐 Testing Web Interface...")
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        resp.raise_for_status()
        
        if '<title>' in resp.text and '图像风格匹配' in resp.text:
            print(f"✅ Web interface loaded successfully")
            print(f"   Title: {resp.text.split('<title>')[1].split('</title>')[0]}")
            return True
        else:
            print(f"⚠️ Web interface may not be loading correctly")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("=" * 70)
    print("🧪 Image Style Matching System - Test Suite")
    print("=" * 70)
    
    all_passed = True
    
    # 测试案例列表
    if not test_cases_api():
        all_passed = False
    
    # 测试Web界面
    if not test_web_interface():
        all_passed = False
    
    # 测试分析单个案例
    case_result = test_analyze_case("case_001")
    if not case_result:
        all_passed = False
    
    # 测试分析所有案例
    all_results = test_analyze_all()
    if not all_results:
        all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All tests passed!")
        print("\n📌 You can now use the system:")
        print("   🌐 Web Interface: http://localhost:5001/")
        print("   📚 API Docs: http://localhost:5001/api/cases")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    print("=" * 70)

if __name__ == "__main__":
    try:
        requests.head(BASE_URL, timeout=2)
    except:
        print("❌ Server is not running!")
        print("   Please start the server first:")
        print("   PORT=5001 python3 -m src.app")
        sys.exit(1)
    
    main()
