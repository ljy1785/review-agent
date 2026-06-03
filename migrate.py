import sqlite3
import pymysql
import json
from dotenv import load_dotenv
import os

load_dotenv()

# SQLite 연결
sqlite_conn = sqlite3.connect("reviews.db")
sqlite_conn.row_factory = sqlite3.Row
sqlite_cursor = sqlite_conn.cursor()

# MariaDB 연결
maria_conn = pymysql.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    charset="utf8mb4"
)
maria_cursor = maria_conn.cursor()

# reviews 마이그레이션
sqlite_cursor.execute("SELECT * FROM reviews")
reviews = sqlite_cursor.fetchall()

for row in reviews:
    maria_cursor.execute("""
        INSERT INTO reviews (id, review, agent_aspect, agent_label, agent_evidence, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        row["id"],
        row["review"],
        row["agent_aspect"],
        row["agent_label"],
        row["agent_evidence"],
        row["updated_at"]
    ))

print(f"reviews 마이그레이션 완료: {len(reviews)}건")

# aspects 마이그레이션
sqlite_cursor.execute("SELECT * FROM aspects")
aspects = sqlite_cursor.fetchall()

for row in aspects:
    maria_cursor.execute("""
        INSERT INTO aspects (id, aspect, status, created_at)
        VALUES (%s, %s, %s, %s)
    """, (
        row["id"],
        row["aspect"],
        row["status"],
        row["created_at"]
    ))

print(f"aspects 마이그레이션 완료: {len(aspects)}건")

maria_conn.commit()
sqlite_conn.close()
maria_conn.close()
print("마이그레이션 완료!")