#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    dbname='pikachu',
    user='postgres',
    password='',
    host='localhost',
    port='5432'
)

cur = conn.cursor()
cur.execute("SELECT file_path FROM image_features LIMIT 5;")
rows = cur.fetchall()

print("数据库中的文件路径示例:")
for row in rows:
    print(f"  {row[0]}")

cur.execute("SELECT COUNT(*) FROM image_features WHERE file_path LIKE '%blink-edge%';")
count = cur.fetchone()[0]
print(f"\n包含 'blink-edge' 的记录数: {count}")

conn.close()
