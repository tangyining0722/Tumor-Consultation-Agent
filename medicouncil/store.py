import sqlite3
import json
from datetime import datetime, timezone
from .config import settings

def connect():
    db=sqlite3.connect(settings.db_path)
    db.execute("CREATE TABLE IF NOT EXISTS consultations (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, input TEXT NOT NULL, result_json TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS reading_chunks (doc_hash TEXT NOT NULL, provider TEXT NOT NULL, idx INTEGER NOT NULL, result TEXT NOT NULL, PRIMARY KEY(doc_hash,provider,idx))")
    db.commit()
    return db

def save_consultation(user_input, result):
    with connect() as db:
        cur=db.execute("INSERT INTO consultations(created_at,input,result_json) VALUES (?,?,?)", (datetime.now(timezone.utc).isoformat(),user_input,result.model_dump_json()))
        return cur.lastrowid

def get_chunk(doc_hash, provider, idx):
    with connect() as db:
        row=db.execute("SELECT result FROM reading_chunks WHERE doc_hash=? AND provider=? AND idx=?",(doc_hash,provider,idx)).fetchone()
    return row[0] if row else None

def save_chunk(doc_hash, provider, idx, result):
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO reading_chunks(doc_hash,provider,idx,result) VALUES (?,?,?,?)",(doc_hash,provider,idx,result))
