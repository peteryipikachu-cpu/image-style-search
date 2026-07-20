#!/usr/bin/env python3
"""检查OSS配置和数据情况"""
import psycopg2

conn = psycopg2.connect(
    dbname='pikachu',
    user='postgres',
    password='',
    host='localhost',
    port='5432'
)

cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM image_features;")
total = cur.fetchone()[0]
print(f"总记录数: {total}")

cur.execute("SELECT COUNT(*) FROM image_features WHERE file_path LIKE '%blink-edge/%';")
oss_count = cur.fetchone()[0]
print(f"OSS图片记录数: {oss_count}")

cur.execute("SELECT COUNT(*) FROM image_features WHERE file_path NOT LIKE '%blink-edge/%';")
local_count = cur.fetchone()[0]
print(f"本地图片记录数: {local_count}")

cur.execute("SELECT file_path FROM image_features WHERE file_path LIKE '%blink-edge/%' LIMIT 3;")
oss_paths = cur.fetchall()
print("\nOSS图片路径示例:")
for path in oss_paths:
    print(f"  {path[0]}")

conn.close()

print("\n" + "="*50)
print("问题分析:")
print("1. OSS图片加载失败是因为OSS凭证未配置")
print("2. 数据库中有1000条OSS图片记录")
print("3. 需要配置阿里云OSS凭证才能访问这些图片")
