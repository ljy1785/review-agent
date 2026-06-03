import os
import pymysql
import json
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER", "agent"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "reviewdb"),
        charset="utf8mb4"
    )

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            review         TEXT,
            agent_aspect   TEXT,
            agent_label    TEXT,
            agent_evidence TEXT,
            updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aspects (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            aspect     TEXT NOT NULL UNIQUE,
            status     TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def insert_review(review: str, items: list):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reviews (review, agent_aspect, agent_label, agent_evidence)
        VALUES (%s, %s, %s, %s)
    """, (
        review,
        json.dumps([i["aspect"]   for i in items], ensure_ascii=False),
        json.dumps([i["label"]    for i in items], ensure_ascii=False),
        json.dumps([i["evidence"] for i in items], ensure_ascii=False),
    ))
    conn.commit()
    conn.close()

def get_reviews():
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM reviews ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows