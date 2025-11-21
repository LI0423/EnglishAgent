import os
import sqlite3
import time
import json
from typing import Optional, Tuple, Any, Dict


DB_PATH = os.environ.get("IELTS_AGENT_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "ielts_agent.db"))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    try:
        # Run all migrations in order
        mig_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")
        if os.path.isdir(mig_dir):
            for name in sorted(os.listdir(mig_dir)):
                if name.endswith('.sql'):
                    with open(os.path.join(mig_dir, name), "r", encoding="utf-8") as f:
                        conn.executescript(f.read())
        else:
            # Fallback minimal schema
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id TEXT PRIMARY KEY,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  email TEXT,
                  created_at INTEGER
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                  id TEXT PRIMARY KEY,
                  topic TEXT,
                  type TEXT DEFAULT 'speaking',
                  parts_json TEXT,
                  transcript_text TEXT DEFAULT '',
                  transcript_id TEXT,
                  status TEXT DEFAULT 'in-progress',
                  duration INTEGER DEFAULT 0,
                  accuracy REAL DEFAULT 0.0,
                  created_at INTEGER
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transcripts (
                  id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL,
                  text TEXT,
                  created_at INTEGER
                );
                """
            )
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
              session_id TEXT PRIMARY KEY,
              FC REAL, LR REAL, GR REAL, PR REAL, overall REAL,
              created_at INTEGER
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cur.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cur.fetchone()
    finally:
        conn.close()


def create_user(user_id: str, username: str, password_hash: str, email: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    conn = get_conn()
    try:
        conn.execute("INSERT INTO users (id, username, password_hash, email, created_at) VALUES (?, ?, ?, ?, ?)", (user_id, username, password_hash, email, int(time.time())))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, str(e)
    finally:
        conn.close()


# Session DAO
def create_session(session_id: str, topic: str, parts: list[dict]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO sessions (id, topic, parts_json, transcript_text, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, topic, json.dumps(parts, ensure_ascii=False), "", int(time.time())),
        )
        # insert normalized parts
        for p in parts:
            conn.execute(
                "INSERT INTO session_parts (session_id, idx, type, prompt) VALUES (?, ?, ?, ?)",
                (session_id, int(p.get("index") or p.get("idx") or 0), str(p.get("type") or "part"), str(p.get("prompt") or "")),
            )
        conn.commit()
    finally:
        conn.close()


def append_session_transcript(session_id: str, text_partial: str) -> None:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT transcript_text FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Session not found")
        new_text = ((row["transcript_text"] or "") + text_partial + " ").strip()
        conn.execute("UPDATE sessions SET transcript_text = ? WHERE id = ?", (new_text, session_id))
        conn.commit()
    finally:
        conn.close()


def finish_session(session_id: str, transcript_id: str) -> None:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT transcript_text FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Session not found")
        text = (row["transcript_text"] or "").strip()
        conn.execute(
            "INSERT INTO transcripts (id, session_id, text, created_at) VALUES (?, ?, ?, ?)",
            (transcript_id, session_id, text, int(time.time())),
        )
        conn.execute("UPDATE sessions SET transcript_id = ? WHERE id = ?", (transcript_id, session_id))
        conn.commit()
    finally:
        conn.close()


def get_transcript(transcript_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM transcripts WHERE id = ?", (transcript_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            return None
        sess = dict(row)
        cur2 = conn.execute("SELECT idx, type, prompt FROM session_parts WHERE session_id = ? ORDER BY idx ASC", (session_id,))
        sess["parts"] = [dict(r) for r in cur2.fetchall()]
        return sess
    finally:
        conn.close()


def list_sessions(limit: int = 20, offset: int = 0) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT id, topic, created_at, transcript_id FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# Score DAO
def save_score(session_id: str, fc: float, lr: float, gr: float, pr: float, overall: float) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "REPLACE INTO scores (session_id, FC, LR, GR, PR, overall, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, fc, lr, gr, pr, overall, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def get_score(session_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM scores WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


