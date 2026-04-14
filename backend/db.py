import os
import sqlite3
import time
import json
from uuid import uuid4
from typing import Optional, Tuple, Any, Dict


DB_PATH = os.environ.get("IELTS_AGENT_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "ielts_agent.db"))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_vocab_word(word: Any) -> str:
    return str(word or "").strip().lower()


def _dedupe_vocabulary_rows(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        SELECT id, user_id, word, mastery_level, last_reviewed_at, created_at
        FROM vocabulary
        ORDER BY
          user_id ASC,
          lower(trim(word)) ASC,
          mastery_level DESC,
          last_reviewed_at DESC,
          created_at DESC,
          id ASC
        """
    )
    seen_keys: set[tuple[str, str]] = set()
    to_delete: list[str] = []
    for row in cur.fetchall():
        user_id = str(row["user_id"] or "").strip()
        word_key = _normalize_vocab_word(row["word"])
        if not user_id or not word_key:
            continue
        key = (user_id, word_key)
        if key in seen_keys:
            to_delete.append(str(row["id"]))
        else:
            seen_keys.add(key)
    if to_delete:
        conn.executemany("DELETE FROM vocabulary WHERE id = ?", [(x,) for x in to_delete])
    return len(to_delete)


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
            # idempotent schema hardening for legacy DBs
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON sessions(user_id, created_at)")
            except sqlite3.OperationalError:
                pass
        else:
            # Fallback minimal schema
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id TEXT PRIMARY KEY,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  email TEXT,
                  phone TEXT UNIQUE,
                  created_at INTEGER
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                  id TEXT PRIMARY KEY,
                  user_id TEXT,
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
                CREATE TABLE IF NOT EXISTS session_parts (
                  session_id TEXT,
                  idx INTEGER,
                  type TEXT,
                  prompt TEXT,
                  PRIMARY KEY (session_id, idx)
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
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
              user_id TEXT PRIMARY KEY,
              target_band REAL,
              current_band_overall REAL,
              current_band_listening REAL,
              current_band_reading REAL,
              current_band_writing REAL,
              current_band_speaking REAL,
              skill_vocabulary REAL,
              skill_grammar REAL,
              skill_pronunciation REAL,
              skill_fluency REAL,
              skill_coherence REAL,
              learning_total_hours REAL,
              learning_sessions_count INTEGER,
              learning_streak_days INTEGER,
              learning_avg_daily_minutes REAL,
              weaknesses TEXT,
              strong_areas TEXT,
              created_at INTEGER,
              updated_at INTEGER
            );
            """
        )
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS diagnostic_sessions (
              id TEXT PRIMARY KEY,
              user_id TEXT,
              start_time INTEGER,
              end_time INTEGER,
              modules TEXT,
              total_questions INTEGER,
              completed_questions INTEGER,
              estimated_band REAL,
              created_at INTEGER
            );
            """
        )
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS diagnostic_reports (
              id TEXT PRIMARY KEY,
              session_id TEXT,
              overall_band REAL,
              module_scores TEXT,
              weaknesses TEXT,
              recommendations TEXT,
              generated_at INTEGER
            );
            """
        )
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_plans (
              id TEXT PRIMARY KEY,
              user_id TEXT,
              target_band REAL,
              start_date INTEGER,
              end_date INTEGER,
              daily_minutes INTEGER,
              focus_modules TEXT,
              status TEXT,
              created_at INTEGER
            );
            """
        )
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_tasks (
              id TEXT PRIMARY KEY,
              plan_id TEXT,
              date INTEGER,
              tasks TEXT,
              completed INTEGER,
              created_at INTEGER,
              updated_at INTEGER
            );
            """
        )
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mistakes (
              id TEXT PRIMARY KEY,
              user_id TEXT,
              module TEXT,
              question_id TEXT,
              question_type TEXT,
              error_type TEXT,
              content TEXT,
              user_answer TEXT,
              correct_answer TEXT,
              explanation TEXT,
              difficulty TEXT,
              tags TEXT,
              created_at INTEGER,
              last_reviewed_at INTEGER,
              next_review_date INTEGER,
              mastery_level REAL
            );
            """
        )
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vocabulary (
              id TEXT PRIMARY KEY,
              user_id TEXT,
              word TEXT,
              definition TEXT,
              examples TEXT,
              pronunciation TEXT,
              part_of_speech TEXT,
              tags TEXT,
              source_module TEXT,
              mastery_level REAL,
              last_reviewed_at INTEGER,
              next_review_date INTEGER,
              created_at INTEGER
            );
            """
        )
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
              id TEXT PRIMARY KEY,
              user_id TEXT,
              type TEXT,
              title TEXT,
              content TEXT,
              scheduled_at INTEGER,
              sent_at INTEGER,
              status TEXT DEFAULT 'pending',
              channel TEXT,
              metadata TEXT,
              created_at INTEGER
            );
            """
        )
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminder_preferences (
              user_id TEXT PRIMARY KEY,
              enabled INTEGER DEFAULT 1,
              channels TEXT,
              preferred_times TEXT,
              quiet_hours TEXT,
              created_at INTEGER,
              updated_at INTEGER
            );
            """
        )
            conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_events (
              event_id TEXT PRIMARY KEY,
              user_id TEXT,
              event_type TEXT,
              event_name TEXT,
              properties TEXT,
              timestamp INTEGER,
              created_at INTEGER
            );
            """
        )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_activities (
              id TEXT PRIMARY KEY,
              user_id TEXT,
              activity_type TEXT,
              module TEXT,
              duration INTEGER,
              score REAL,
              metadata TEXT,
              created_at INTEGER,
              updated_at INTEGER
                );
                """
        )
        # vocabulary hardening: clean duplicated words first, then enforce uniqueness
        _dedupe_vocabulary_rows(conn)
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_vocabulary_user_word_norm
            ON vocabulary(user_id, lower(trim(word)))
            WHERE word IS NOT NULL AND trim(word) <> ''
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


def create_user(user_id: str, username: str, password_hash: str, email: Optional[str] = None, phone: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    conn = get_conn()
    try:
        conn.execute("INSERT INTO users (id, username, password_hash, email, phone, created_at) VALUES (?, ?, ?, ?, ?, ?)", (user_id, username, password_hash, email, phone, int(time.time())))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, str(e)
    finally:
        conn.close()


def get_user_by_phone(phone: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,))
        return cur.fetchone()
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
        return cur.fetchone()
    finally:
        conn.close()


def update_user_password_hash(user_id: str, password_hash: str) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def create_password_reset_token(token: str, user_id: str, expires_at: int) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO password_reset_tokens (token, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, user_id, int(expires_at), int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def get_password_reset_token(token: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM password_reset_tokens WHERE token = ?", (token,))
        return cur.fetchone()
    finally:
        conn.close()


def delete_password_reset_token(token: str) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM password_reset_tokens WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()


def cleanup_expired_password_reset_tokens(now_ts: Optional[int] = None) -> int:
    conn = get_conn()
    try:
        now_value = int(now_ts or time.time())
        cur = conn.execute(
            "DELETE FROM password_reset_tokens WHERE expires_at <= ?",
            (now_value,),
        )
        conn.commit()
        return int(cur.rowcount or 0)
    finally:
        conn.close()


def record_password_reset_attempt(account_key: str, requested_at: Optional[int] = None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO password_reset_attempts (account_key, requested_at)
            VALUES (?, ?)
            """,
            (account_key, int(requested_at or time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def count_recent_password_reset_attempts(account_key: str, window_seconds: int = 3600) -> int:
    conn = get_conn()
    try:
        cutoff = int(time.time()) - max(1, int(window_seconds))
        cur = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM password_reset_attempts
            WHERE account_key = ? AND requested_at >= ?
            """,
            (account_key, cutoff),
        )
        row = cur.fetchone()
        return int(row["cnt"] or 0) if row else 0
    finally:
        conn.close()


def create_password_reset_code(
    account_key: str,
    user_id: str,
    channel: str,
    code: str,
    expires_at: int,
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO password_reset_codes (
              account_key, user_id, channel, code, attempts, expires_at, created_at
            ) VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
            (account_key, user_id, channel, code, int(expires_at), int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def get_password_reset_code(account_key: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM password_reset_codes WHERE account_key = ?",
            (account_key,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def increment_password_reset_code_attempts(account_key: str) -> int:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE password_reset_codes SET attempts = attempts + 1 WHERE account_key = ?",
            (account_key,),
        )
        conn.commit()
        cur = conn.execute(
            "SELECT attempts FROM password_reset_codes WHERE account_key = ?",
            (account_key,),
        )
        row = cur.fetchone()
        return int(row["attempts"] or 0) if row else 0
    finally:
        conn.close()


def delete_password_reset_code(account_key: str) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM password_reset_codes WHERE account_key = ?", (account_key,))
        conn.commit()
    finally:
        conn.close()


def cleanup_expired_password_reset_codes(now_ts: Optional[int] = None) -> int:
    conn = get_conn()
    try:
        now_value = int(now_ts or time.time())
        cur = conn.execute(
            "DELETE FROM password_reset_codes WHERE expires_at <= ?",
            (now_value,),
        )
        conn.commit()
        return int(cur.rowcount or 0)
    finally:
        conn.close()


# Session DAO
def create_session(session_id: str, topic: str, parts: list[dict], user_id: Optional[str] = None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO sessions (id, user_id, topic, parts_json, transcript_text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, user_id, topic, json.dumps(parts, ensure_ascii=False), "", int(time.time())),
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


def append_session_transcript(session_id: str, text_partial: str, user_id: Optional[str] = None) -> None:
    conn = get_conn()
    try:
        if user_id:
            cur = conn.execute("SELECT transcript_text FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
        else:
            cur = conn.execute("SELECT transcript_text FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Session not found")
        new_text = ((row["transcript_text"] or "") + text_partial + " ").strip()
        if user_id:
            conn.execute("UPDATE sessions SET transcript_text = ? WHERE id = ? AND user_id = ?", (new_text, session_id, user_id))
        else:
            conn.execute("UPDATE sessions SET transcript_text = ? WHERE id = ?", (new_text, session_id))
        conn.commit()
    finally:
        conn.close()


def finish_session(session_id: str, transcript_id: str, user_id: Optional[str] = None) -> None:
    conn = get_conn()
    try:
        if user_id:
            cur = conn.execute("SELECT transcript_text FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
        else:
            cur = conn.execute("SELECT transcript_text FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Session not found")
        text = (row["transcript_text"] or "").strip()
        conn.execute(
            "INSERT INTO transcripts (id, session_id, text, created_at) VALUES (?, ?, ?, ?)",
            (transcript_id, session_id, text, int(time.time())),
        )
        if user_id:
            conn.execute("UPDATE sessions SET transcript_id = ? WHERE id = ? AND user_id = ?", (transcript_id, session_id, user_id))
        else:
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


def get_transcript_for_user(transcript_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT t.*
            FROM transcripts t
            JOIN sessions s ON s.id = t.session_id
            WHERE t.id = ? AND s.user_id = ?
            """,
            (transcript_id, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_session(session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        if user_id:
            cur = conn.execute("SELECT * FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
        else:
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


def list_sessions(user_id: Optional[str] = None, limit: int = 20, offset: int = 0) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        if user_id:
            cur = conn.execute(
                "SELECT id, topic, created_at, transcript_id FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            )
        else:
            cur = conn.execute(
                "SELECT id, topic, created_at, transcript_id FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
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


# User Profile DAO
def create_user_profile(user_id: str, profile_data: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO user_profiles (
              user_id, target_band, current_band_overall, current_band_listening, 
              current_band_reading, current_band_writing, current_band_speaking, 
              skill_vocabulary, skill_grammar, skill_pronunciation, skill_fluency, 
              skill_coherence, learning_total_hours, learning_sessions_count, 
              learning_streak_days, learning_avg_daily_minutes, weaknesses, 
              strong_areas, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                profile_data.get('target_band', 0.0),
                profile_data.get('current_band_overall', 0.0),
                profile_data.get('current_band_listening', 0.0),
                profile_data.get('current_band_reading', 0.0),
                profile_data.get('current_band_writing', 0.0),
                profile_data.get('current_band_speaking', 0.0),
                profile_data.get('skill_vocabulary', 0.0),
                profile_data.get('skill_grammar', 0.0),
                profile_data.get('skill_pronunciation', 0.0),
                profile_data.get('skill_fluency', 0.0),
                profile_data.get('skill_coherence', 0.0),
                profile_data.get('learning_total_hours', 0.0),
                profile_data.get('learning_sessions_count', 0),
                profile_data.get('learning_streak_days', 0),
                profile_data.get('learning_avg_daily_minutes', 0.0),
                json.dumps(profile_data.get('weaknesses', [])),
                json.dumps(profile_data.get('strong_areas', [])),
                int(time.time()),
                int(time.time())
            )
        )
        conn.commit()
    finally:
        conn.close()


def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        profile = dict(row)
        profile['weaknesses'] = json.loads(profile['weaknesses']) if profile['weaknesses'] else []
        profile['strong_areas'] = json.loads(profile['strong_areas']) if profile['strong_areas'] else []
        return profile
    finally:
        conn.close()


# Diagnostic DAO
def create_diagnostic_session(session_id: str, user_id: str, modules: list) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO diagnostic_sessions (id, user_id, start_time, modules, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, int(time.time()), json.dumps(modules), int(time.time()))
        )
        conn.commit()
    finally:
        conn.close()


def complete_diagnostic_session(session_id: str, end_time: int, total_questions: int, completed_questions: int, estimated_band: float) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE diagnostic_sessions SET end_time = ?, total_questions = ?, completed_questions = ?, estimated_band = ? WHERE id = ?",
            (end_time, total_questions, completed_questions, estimated_band, session_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_diagnostic_session(session_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM diagnostic_sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_diagnostic_report(report_id: str, session_id: str, report_data: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO diagnostic_reports (id, session_id, overall_band, module_scores, weaknesses, recommendations, generated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                report_id,
                session_id,
                report_data.get('overall_band', 0.0),
                json.dumps(report_data.get('module_scores', {})),
                json.dumps(report_data.get('weaknesses', [])),
                json.dumps(report_data.get('recommendations', [])),
                int(time.time())
            )
        )
        conn.commit()
    finally:
        conn.close()


def get_diagnostic_report(session_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM diagnostic_reports WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            return None
        report = dict(row)
        report['module_scores'] = json.loads(report['module_scores']) if report['module_scores'] else {}
        report['weaknesses'] = json.loads(report['weaknesses']) if report['weaknesses'] else []
        report['recommendations'] = json.loads(report['recommendations']) if report['recommendations'] else []
        return report
    finally:
        conn.close()


def list_user_diagnostic_reports(user_id: str, limit: int = 20) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT
              r.id,
              r.session_id,
              r.overall_band,
              r.module_scores,
              r.weaknesses,
              r.recommendations,
              r.generated_at
            FROM diagnostic_reports r
            JOIN diagnostic_sessions s ON r.session_id = s.id
            WHERE s.user_id = ?
            ORDER BY r.generated_at DESC
            LIMIT ?
            """,
            (str(user_id), max(1, int(limit))),
        )
        rows = []
        for row in cur.fetchall():
            item = dict(row)
            item["module_scores"] = json.loads(item["module_scores"]) if item.get("module_scores") else []
            item["weaknesses"] = json.loads(item["weaknesses"]) if item.get("weaknesses") else []
            item["recommendations"] = json.loads(item["recommendations"]) if item.get("recommendations") else []
            rows.append(item)
        return rows
    finally:
        conn.close()


# Learning Plan DAO
def create_learning_plan(plan_id: str, user_id: str, plan_data: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO learning_plans (
              id, user_id, target_band, start_date, end_date, 
              daily_minutes, focus_modules, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                user_id,
                plan_data.get('target_band', 0.0),
                plan_data.get('start_date', int(time.time())),
                plan_data.get('end_date', int(time.time()) + 7 * 24 * 3600),
                plan_data.get('daily_minutes', 30),
                json.dumps(plan_data.get('focus_modules', [])),
                plan_data.get('status', 'active'),
                int(time.time())
            )
        )
        conn.commit()
    finally:
        conn.close()


def get_learning_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM learning_plans WHERE id = ?", (plan_id,))
        row = cur.fetchone()
        if not row:
            return None
        plan = dict(row)
        plan['focus_modules'] = json.loads(plan['focus_modules']) if plan['focus_modules'] else []
        return plan
    finally:
        conn.close()


def list_user_plans(user_id: str) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM learning_plans WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        plans = []
        for row in cur.fetchall():
            plan = dict(row)
            plan['focus_modules'] = json.loads(plan['focus_modules']) if plan['focus_modules'] else []
            plans.append(plan)
        return plans
    finally:
        conn.close()


def get_latest_user_plan(user_id: str) -> Optional[Dict[str, Any]]:
    plans = list_user_plans(user_id)
    if not plans:
        return None
    for plan in plans:
        if str(plan.get("status", "")).lower() == "active":
            return plan
    return plans[0]


def update_plan_status(plan_id: str, status: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE learning_plans SET status = ? WHERE id = ?",
            (status, plan_id)
        )
        conn.commit()
    finally:
        conn.close()


def update_learning_plan_settings(
    plan_id: str,
    *,
    daily_minutes: Optional[int] = None,
    focus_modules: Optional[list[str]] = None,
    status: Optional[str] = None,
) -> None:
    updates: list[str] = []
    params: list[Any] = []
    if daily_minutes is not None:
        updates.append("daily_minutes = ?")
        params.append(int(daily_minutes))
    if focus_modules is not None:
        updates.append("focus_modules = ?")
        params.append(json.dumps([str(x) for x in focus_modules if str(x).strip()]))
    if status is not None:
        updates.append("status = ?")
        params.append(str(status))
    if not updates:
        return

    params.append(str(plan_id))
    conn = get_conn()
    try:
        conn.execute(
            f"UPDATE learning_plans SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def create_plan_calibration_log(
    log_id: str,
    *,
    plan_id: str,
    user_id: str,
    before_daily_minutes: Optional[int],
    after_daily_minutes: Optional[int],
    before_focus_modules: Optional[list[str]],
    after_focus_modules: Optional[list[str]],
    source: str = "manual",
    note: str = "",
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO plan_calibration_logs (
              id, plan_id, user_id, before_daily_minutes, after_daily_minutes,
              before_focus_modules, after_focus_modules, source, note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(log_id),
                str(plan_id),
                str(user_id),
                before_daily_minutes if before_daily_minutes is not None else None,
                after_daily_minutes if after_daily_minutes is not None else None,
                json.dumps(before_focus_modules or []),
                json.dumps(after_focus_modules or []),
                str(source or "manual"),
                str(note or ""),
                int(time.time()),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_plan_calibration_logs(plan_id: str, limit: int = 20) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM plan_calibration_logs
            WHERE plan_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(plan_id), max(1, int(limit))),
        )
        rows: list[Dict[str, Any]] = []
        for row in cur.fetchall():
            item = dict(row)
            item["before_focus_modules"] = json.loads(item["before_focus_modules"]) if item.get("before_focus_modules") else []
            item["after_focus_modules"] = json.loads(item["after_focus_modules"]) if item.get("after_focus_modules") else []
            rows.append(item)
        return rows
    finally:
        conn.close()


def _infer_task_module(task: Dict[str, Any]) -> str:
    raw_module = str(task.get("module") or "").strip().lower()
    if raw_module:
        return raw_module
    raw_text = f"{task.get('title', '')} {task.get('description', '')}".lower()
    if "听力" in raw_text or "listening" in raw_text:
        return "listening"
    if "阅读" in raw_text or "reading" in raw_text:
        return "reading"
    if "写作" in raw_text or "writing" in raw_text:
        return "writing"
    if "口语" in raw_text or "speaking" in raw_text:
        return "speaking"
    if "词汇" in raw_text or "vocabulary" in raw_text:
        return "vocabulary"
    return "unknown"


def get_plan_execution_health(plan_id: str, days: int = 14, now_ts: Optional[int] = None) -> Dict[str, Any]:
    now = int(now_ts or time.time())
    days = max(1, min(90, int(days)))
    start_ts = now - days * 24 * 3600
    tasks = get_daily_tasks_by_plan(plan_id)
    window_rows = [x for x in tasks if int(x.get("date") or 0) >= start_ts]

    task_total = 0
    task_done = 0
    scheduled_days = len(window_rows)
    completed_days = 0
    daily_trend: list[Dict[str, Any]] = []
    module_stats: Dict[str, Dict[str, Any]] = {}

    for row in sorted(window_rows, key=lambda x: int(x.get("date") or 0)):
        date_ts = int(row.get("date") or 0)
        date_text = time.strftime("%Y-%m-%d", time.localtime(date_ts)) if date_ts else ""
        items = row.get("tasks") or []
        total = len(items)
        done = sum(1 for t in items if bool(t.get("completed")))
        rate = (done / total) * 100 if total > 0 else 0.0
        if total > 0 and done == total:
            completed_days += 1
        task_total += total
        task_done += done
        daily_trend.append(
            {
                "date": date_text,
                "date_ts": date_ts,
                "done": done,
                "total": total,
                "completion_rate": round(rate, 2),
            }
        )

        for t in items:
            module = _infer_task_module(t)
            if module not in module_stats:
                module_stats[module] = {"module": module, "done": 0, "total": 0}
            module_stats[module]["total"] += 1
            if bool(t.get("completed")):
                module_stats[module]["done"] += 1

    avg_completion = (task_done / task_total) * 100 if task_total > 0 else 0.0
    day_completion_rate = (completed_days / scheduled_days) * 100 if scheduled_days > 0 else 0.0

    streak = 0
    by_date = {x["date"]: x for x in daily_trend}
    for idx in range(days):
        cur_ts = now - idx * 24 * 3600
        cur_day = time.strftime("%Y-%m-%d", time.localtime(cur_ts))
        row = by_date.get(cur_day)
        if not row or row["total"] <= 0 or row["done"] < row["total"]:
            break
        streak += 1

    module_rows: list[Dict[str, Any]] = []
    for m in module_stats.values():
        rate = (m["done"] / m["total"]) * 100 if m["total"] > 0 else 0.0
        module_rows.append(
            {
                "module": m["module"],
                "done": m["done"],
                "total": m["total"],
                "completion_rate": round(rate, 2),
            }
        )
    module_rows.sort(key=lambda x: x["total"], reverse=True)

    health_level = "healthy"
    if avg_completion < 50 or day_completion_rate < 40:
        health_level = "at_risk"
    elif avg_completion < 75:
        health_level = "watch"

    return {
        "plan_id": str(plan_id),
        "days": days,
        "scheduled_days": scheduled_days,
        "completed_days": completed_days,
        "day_completion_rate": round(day_completion_rate, 2),
        "task_total": task_total,
        "task_done": task_done,
        "task_completion_rate": round(avg_completion, 2),
        "streak_days": streak,
        "health_level": health_level,
        "daily_trend": daily_trend,
        "module_stats": module_rows,
    }


def get_plan_intervention_status(plan_id: str, days: int = 14, now_ts: Optional[int] = None) -> Dict[str, Any]:
    now = int(now_ts or time.time())
    days = max(1, min(90, int(days)))
    start_ts = now - days * 24 * 3600
    rows = get_daily_tasks_by_plan(plan_id)

    total = 0
    done = 0
    module_map: Dict[str, Dict[str, Any]] = {}
    daily_map: Dict[int, Dict[str, Any]] = {}
    latest_batch_id = ""
    latest_batch_created_at = 0
    batch_counts: Dict[str, int] = {}

    for row in rows:
        date_ts = int(row.get("date") or 0)
        if date_ts < start_ts:
            continue
        day_key = int(date_ts // 86400) * 86400
        if day_key not in daily_map:
            daily_map[day_key] = {"day_start": day_key, "done": 0, "total": 0}
        for item in (row.get("tasks") or []):
            if str(item.get("kind") or "") != "intervention":
                continue
            total += 1
            daily_map[day_key]["total"] += 1
            module = _infer_task_module(item)
            if module not in module_map:
                module_map[module] = {"module": module, "done": 0, "total": 0}
            module_map[module]["total"] += 1
            if bool(item.get("completed")):
                done += 1
                daily_map[day_key]["done"] += 1
                module_map[module]["done"] += 1

            batch_id = str(item.get("intervention_batch_id") or "")
            if batch_id:
                batch_counts[batch_id] = batch_counts.get(batch_id, 0) + 1
                created_at = int(item.get("intervention_created_at") or 0)
                if created_at >= latest_batch_created_at:
                    latest_batch_created_at = created_at
                    latest_batch_id = batch_id

    daily_trend: list[Dict[str, Any]] = []
    for i in range(days):
        day_start = int((start_ts // 86400) * 86400 + i * 86400)
        row = daily_map.get(day_start, {"done": 0, "total": 0})
        rate = (row["done"] / row["total"] * 100) if row["total"] > 0 else 0.0
        daily_trend.append(
            {
                "day_start": day_start,
                "date": time.strftime("%m-%d", time.localtime(day_start)),
                "done": int(row["done"]),
                "total": int(row["total"]),
                "completion_rate": round(rate, 2),
            }
        )

    module_rows: list[Dict[str, Any]] = []
    for x in module_map.values():
        rate = (x["done"] / x["total"] * 100) if x["total"] > 0 else 0.0
        module_rows.append(
            {
                "module": x["module"],
                "done": int(x["done"]),
                "total": int(x["total"]),
                "completion_rate": round(rate, 2),
            }
        )
    module_rows.sort(key=lambda x: x["total"], reverse=True)

    overall_rate = (done / total * 100) if total > 0 else 0.0
    return {
        "plan_id": str(plan_id),
        "days": days,
        "intervention_total": int(total),
        "intervention_done": int(done),
        "intervention_completion_rate": round(overall_rate, 2),
        "latest_batch_id": latest_batch_id,
        "latest_batch_created_at": int(latest_batch_created_at),
        "batch_count": len(batch_counts),
        "daily_trend": daily_trend,
        "module_stats": module_rows,
    }


def create_daily_task(task_id: str, plan_id: str, date: int, tasks: list) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO daily_tasks (id, plan_id, date, tasks, completed, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task_id, plan_id, date, json.dumps(tasks), 0, int(time.time()), int(time.time()))
        )
        conn.commit()
    finally:
        conn.close()


def get_daily_task(task_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM daily_tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        if not row:
            return None
        task = dict(row)
        task['tasks'] = json.loads(task['tasks']) if task['tasks'] else []
        return task
    finally:
        conn.close()


def get_daily_tasks_by_plan(plan_id: str) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM daily_tasks WHERE plan_id = ? ORDER BY date ASC", (plan_id,))
        tasks = []
        for row in cur.fetchall():
            task = dict(row)
            task['tasks'] = json.loads(task['tasks']) if task['tasks'] else []
            tasks.append(task)
        return tasks
    finally:
        conn.close()


def get_daily_task_by_date(plan_id: str, date: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM daily_tasks WHERE plan_id = ? AND date = ?", (plan_id, date))
        row = cur.fetchone()
        if not row:
            return None
        task = dict(row)
        task['tasks'] = json.loads(task['tasks']) if task['tasks'] else []
        return task
    finally:
        conn.close()


def update_task_completion(task_id: str, completed: bool) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE daily_tasks SET completed = ?, updated_at = ? WHERE id = ?",
            (1 if completed else 0, int(time.time()), task_id)
        )
        conn.commit()
    finally:
        conn.close()


def update_task_progress(task_id: str, progress: dict) -> None:
    conn = get_conn()
    try:
        # 获取当前任务
        task = get_daily_task(task_id)
        if not task:
            return
        
        # 更新任务进度
        tasks = task['tasks']
        for i, t in enumerate(tasks):
            if t.get('id') == progress.get('task_id'):
                tasks[i]['completed'] = progress.get('completed', False)
                tasks[i]['progress'] = progress.get('progress', 0)
                tasks[i]['time_spent'] = progress.get('time_spent', 0)
                break
        
        # 检查是否所有任务都完成
        all_completed = all(t.get('completed', False) for t in tasks)
        
        conn.execute(
            "UPDATE daily_tasks SET tasks = ?, completed = ?, updated_at = ? WHERE id = ?",
            (json.dumps(tasks), 1 if all_completed else 0, int(time.time()), task_id)
        )
        conn.commit()
    finally:
        conn.close()


def append_daily_task_items(task_id: str, items: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM daily_tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        if not row:
            return None
        task = dict(row)
        existing_tasks = json.loads(task["tasks"]) if task.get("tasks") else []
        merged_tasks = existing_tasks + list(items or [])
        all_completed = all(bool(x.get("completed")) for x in merged_tasks) if merged_tasks else False
        now = int(time.time())
        conn.execute(
            "UPDATE daily_tasks SET tasks = ?, completed = ?, updated_at = ? WHERE id = ?",
            (json.dumps(merged_tasks), 1 if all_completed else 0, now, task_id),
        )
        conn.commit()
        task["tasks"] = merged_tasks
        task["completed"] = 1 if all_completed else 0
        task["updated_at"] = now
        return task
    finally:
        conn.close()


def get_plan_progress(plan_id: str) -> Dict[str, Any]:
    conn = get_conn()
    try:
        # 获取所有任务
        tasks = get_daily_tasks_by_plan(plan_id)
        
        if not tasks:
            return {
                'total_tasks': 0,
                'completed_tasks': 0,
                'completion_rate': 0.0,
                'tasks': []
            }
        
        total_tasks = len(tasks)
        completed_tasks = sum(1 for task in tasks if task['completed'])
        completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0.0
        
        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': completion_rate,
            'tasks': tasks
        }
    finally:
        conn.close()


# Writing peer review DAO
def create_writing_submission(
    submission_id: str,
    user_id: str,
    task_type: str,
    topic: str,
    content: str,
) -> None:
    now = int(time.time())
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO writing_submissions (
              id, user_id, task_type, topic, content, status,
              review_count, avg_overall_score, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'open', 0, 0, ?, ?)
            """,
            (
                str(submission_id),
                str(user_id),
                str(task_type),
                str(topic or ""),
                str(content or ""),
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_writing_submission(submission_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM writing_submissions WHERE id = ?", (str(submission_id),))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_user_writing_submissions(user_id: str, limit: int = 20) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT * FROM writing_submissions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(user_id), max(1, int(limit))),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def claim_writing_submission_for_review(reviewer_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT s.*
            FROM writing_submissions s
            WHERE s.user_id != ?
              AND s.status IN ('open', 'in_review')
              AND NOT EXISTS (
                SELECT 1 FROM writing_peer_reviews r
                WHERE r.submission_id = s.id AND r.reviewer_id = ?
              )
            ORDER BY s.created_at ASC
            LIMIT 1
            """,
            (str(reviewer_id), str(reviewer_id)),
        )
        row = cur.fetchone()
        if not row:
            return None
        submission = dict(row)
        if submission.get("status") == "open":
            conn.execute(
                "UPDATE writing_submissions SET status = 'in_review', updated_at = ? WHERE id = ?",
                (int(time.time()), str(submission["id"])),
            )
            conn.commit()
            submission["status"] = "in_review"
        return submission
    finally:
        conn.close()


def create_writing_peer_review(
    review_id: str,
    submission_id: str,
    reviewer_id: str,
    reviewee_id: str,
    tr_score: float,
    cc_score: float,
    lr_score: float,
    gra_score: float,
    overall_score: float,
    strengths: str = "",
    improvements: str = "",
    comment_text: str = "",
    quality_tier: str = "basic",
) -> None:
    now = int(time.time())
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO writing_peer_reviews (
              id, submission_id, reviewer_id, reviewee_id,
              tr_score, cc_score, lr_score, gra_score, overall_score,
              strengths, improvements, comment_text, quality_tier, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(review_id),
                str(submission_id),
                str(reviewer_id),
                str(reviewee_id),
                float(tr_score),
                float(cc_score),
                float(lr_score),
                float(gra_score),
                float(overall_score),
                str(strengths or ""),
                str(improvements or ""),
                str(comment_text or ""),
                str(quality_tier or "basic"),
                now,
            ),
        )

        cur = conn.execute(
            """
            SELECT COUNT(*) AS cnt, AVG(overall_score) AS avg_score
            FROM writing_peer_reviews
            WHERE submission_id = ?
            """,
            (str(submission_id),),
        )
        row = cur.fetchone()
        cnt = int(row["cnt"] or 0)
        avg_score = float(row["avg_score"] or 0.0)
        next_status = "reviewed" if cnt >= 2 else "in_review"
        conn.execute(
            """
            UPDATE writing_submissions
            SET review_count = ?, avg_overall_score = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (cnt, round(avg_score, 3), next_status, now, str(submission_id)),
        )
        conn.commit()
    finally:
        conn.close()


def list_reviews_for_submission(submission_id: str, limit: int = 20) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM writing_peer_reviews
            WHERE submission_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(submission_id), max(1, int(limit))),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def list_received_writing_reviews(user_id: str, limit: int = 30) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT
              r.*,
              s.task_type,
              s.topic,
              s.content
            FROM writing_peer_reviews r
            JOIN writing_submissions s ON s.id = r.submission_id
            WHERE r.reviewee_id = ?
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (str(user_id), max(1, int(limit))),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def get_writing_peer_stats(user_id: str) -> Dict[str, Any]:
    conn = get_conn()
    try:
        user_id = str(user_id)
        sub_row = conn.execute(
            """
            SELECT
              COUNT(*) AS total_submissions,
              SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_submissions,
              SUM(CASE WHEN status = 'in_review' THEN 1 ELSE 0 END) AS in_review_submissions,
              SUM(CASE WHEN status = 'reviewed' THEN 1 ELSE 0 END) AS reviewed_submissions,
              AVG(avg_overall_score) AS avg_received_score
            FROM writing_submissions
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        rev_row = conn.execute(
            """
            SELECT
              COUNT(*) AS total_reviews_written,
              AVG(overall_score) AS avg_given_score,
              SUM(CASE WHEN quality_tier = 'advanced' THEN 1 ELSE 0 END) AS advanced_count,
              SUM(CASE WHEN quality_tier = 'standard' THEN 1 ELSE 0 END) AS standard_count,
              SUM(CASE WHEN quality_tier = 'basic' THEN 1 ELSE 0 END) AS basic_count
            FROM writing_peer_reviews
            WHERE reviewer_id = ?
            """,
            (user_id,),
        ).fetchone()

        points_row = conn.execute(
            """
            SELECT
              COALESCE(SUM(
                CASE quality_tier
                  WHEN 'advanced' THEN 6
                  WHEN 'standard' THEN 3
                  ELSE 1
                END
              ), 0) AS total_points
            FROM writing_peer_reviews
            WHERE reviewer_id = ?
            """,
            (user_id,),
        ).fetchone()

        return {
            "user_id": user_id,
            "total_submissions": int((sub_row["total_submissions"] or 0) if sub_row else 0),
            "open_submissions": int((sub_row["open_submissions"] or 0) if sub_row else 0),
            "in_review_submissions": int((sub_row["in_review_submissions"] or 0) if sub_row else 0),
            "reviewed_submissions": int((sub_row["reviewed_submissions"] or 0) if sub_row else 0),
            "avg_received_score": round(float((sub_row["avg_received_score"] or 0.0) if sub_row else 0.0), 3),
            "total_reviews_written": int((rev_row["total_reviews_written"] or 0) if rev_row else 0),
            "avg_given_score": round(float((rev_row["avg_given_score"] or 0.0) if rev_row else 0.0), 3),
            "quality_counts": {
                "advanced": int((rev_row["advanced_count"] or 0) if rev_row else 0),
                "standard": int((rev_row["standard_count"] or 0) if rev_row else 0),
                "basic": int((rev_row["basic_count"] or 0) if rev_row else 0),
            },
            "total_points": int((points_row["total_points"] or 0) if points_row else 0),
        }
    finally:
        conn.close()


def list_writing_peer_leaderboard(limit: int = 10) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT
              r.reviewer_id AS reviewer_id,
              COUNT(*) AS total_reviews,
              AVG(r.overall_score) AS avg_given_score,
              SUM(CASE WHEN r.quality_tier = 'advanced' THEN 1 ELSE 0 END) AS advanced_count,
              SUM(CASE WHEN r.quality_tier = 'standard' THEN 1 ELSE 0 END) AS standard_count,
              SUM(CASE WHEN r.quality_tier = 'basic' THEN 1 ELSE 0 END) AS basic_count,
              SUM(
                CASE r.quality_tier
                  WHEN 'advanced' THEN 6
                  WHEN 'standard' THEN 3
                  ELSE 1
                END
              ) AS total_points
            FROM writing_peer_reviews r
            GROUP BY r.reviewer_id
            ORDER BY total_points DESC, total_reviews DESC, avg_given_score DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def create_gamification_event(
    event_id: str,
    *,
    user_id: str,
    source: str,
    source_id: str,
    points: int,
    note: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO gamification_events (
              id, user_id, source, source_id, points, note, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(event_id),
                str(user_id),
                str(source),
                str(source_id),
                int(points),
                str(note or ""),
                json.dumps(metadata or {}),
                int(time.time()),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_gamification_total_points(user_id: str) -> int:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(points), 0) AS total FROM gamification_events WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
        return int((row["total"] or 0) if row else 0)
    finally:
        conn.close()


def list_gamification_events(user_id: str, limit: int = 50) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM gamification_events
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(user_id), max(1, int(limit))),
        )
        rows: list[Dict[str, Any]] = []
        for row in cur.fetchall():
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"]) if item.get("metadata") else {}
            rows.append(item)
        return rows
    finally:
        conn.close()


def list_gamification_leaderboard(limit: int = 20) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT
              user_id,
              COALESCE(SUM(points), 0) AS total_points,
              COUNT(*) AS event_count,
              MAX(created_at) AS last_event_at
            FROM gamification_events
            GROUP BY user_id
            ORDER BY total_points DESC, event_count DESC, last_event_at DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def create_gamification_achievement(
    achievement_id: str,
    *,
    user_id: str,
    code: str,
    title: str,
    description: str = "",
    icon: str = "🏅",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO gamification_achievements (
              id, user_id, code, title, description, icon, unlocked_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(achievement_id),
                str(user_id),
                str(code),
                str(title),
                str(description or ""),
                str(icon or "🏅"),
                int(time.time()),
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def list_gamification_achievements(user_id: str, limit: int = 100) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM gamification_achievements
            WHERE user_id = ?
            ORDER BY unlocked_at DESC
            LIMIT ?
            """,
            (str(user_id), max(1, int(limit))),
        )
        rows: list[Dict[str, Any]] = []
        for row in cur.fetchall():
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"]) if item.get("metadata") else {}
            rows.append(item)
        return rows
    finally:
        conn.close()


def create_gamification_redemption(
    redemption_id: str,
    *,
    user_id: str,
    item_code: str,
    item_name: str,
    cost_points: int,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO gamification_redemptions (
              id, user_id, item_code, item_name, cost_points, status, created_at, metadata
            ) VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)
            """,
            (
                str(redemption_id),
                str(user_id),
                str(item_code),
                str(item_name),
                int(cost_points),
                int(time.time()),
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_gamification_redemptions(user_id: str, limit: int = 30) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM gamification_redemptions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(user_id), max(1, int(limit))),
        )
        rows: list[Dict[str, Any]] = []
        for row in cur.fetchall():
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"]) if item.get("metadata") else {}
            rows.append(item)
        return rows
    finally:
        conn.close()


def create_community_post(
    post_id: str,
    *,
    user_id: str,
    post_type: str,
    title: str,
    content: str,
    tags: Optional[list[str]] = None,
    status: str = "published",
    is_anonymous: bool = False,
) -> None:
    now = int(time.time())
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO community_posts (
              id, user_id, post_type, title, content, tags, status, is_anonymous,
              upvotes, downvotes, comment_count, view_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?)
            """,
            (
                str(post_id),
                str(user_id),
                str(post_type),
                str(title),
                str(content),
                json.dumps([str(x).strip() for x in (tags or []) if str(x).strip()]),
                str(status),
                1 if is_anonymous else 0,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_community_post(post_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM community_posts WHERE id = ?", (str(post_id),)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["tags"] = json.loads(item["tags"]) if item.get("tags") else []
        return item
    finally:
        conn.close()


def add_community_post_view(post_id: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE community_posts SET view_count = view_count + 1, updated_at = ? WHERE id = ?",
            (int(time.time()), str(post_id)),
        )
        conn.commit()
    finally:
        conn.close()


def list_community_posts(
    *,
    post_type: Optional[str] = None,
    status: str = "published",
    keyword: str = "",
    limit: int = 20,
    offset: int = 0,
) -> list[Dict[str, Any]]:
    where = ["status = ?"]
    params: list[Any] = [str(status)]
    if post_type:
        where.append("post_type = ?")
        params.append(str(post_type))
    if keyword.strip():
        where.append("(title LIKE ? OR content LIKE ?)")
        like = f"%{keyword.strip()}%"
        params.extend([like, like])
    params.extend([max(1, int(limit)), max(0, int(offset))])

    conn = get_conn()
    try:
        cur = conn.execute(
            f"""
            SELECT *
            FROM community_posts
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params,
        )
        items: list[Dict[str, Any]] = []
        for row in cur.fetchall():
            item = dict(row)
            item["tags"] = json.loads(item["tags"]) if item.get("tags") else []
            items.append(item)
        return items
    finally:
        conn.close()


def create_community_comment(
    comment_id: str,
    *,
    post_id: str,
    user_id: str,
    content: str,
    status: str = "published",
    is_anonymous: bool = False,
) -> None:
    now = int(time.time())
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO community_comments (
              id, post_id, user_id, content, status, is_anonymous,
              upvotes, downvotes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            """,
            (
                str(comment_id),
                str(post_id),
                str(user_id),
                str(content),
                str(status),
                1 if is_anonymous else 0,
                now,
                now,
            ),
        )
        conn.execute(
            "UPDATE community_posts SET comment_count = comment_count + 1, updated_at = ? WHERE id = ?",
            (now, str(post_id)),
        )
        conn.commit()
    finally:
        conn.close()


def list_community_comments(post_id: str, status: str = "published", limit: int = 100) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM community_comments
            WHERE post_id = ? AND status = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (str(post_id), str(status), max(1, int(limit))),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def get_community_comment(comment_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM community_comments WHERE id = ?", (str(comment_id),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _refresh_vote_totals(conn: sqlite3.Connection, target_type: str, target_id: str) -> None:
    row = conn.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN vote = 1 THEN 1 ELSE 0 END), 0) AS upvotes,
          COALESCE(SUM(CASE WHEN vote = -1 THEN 1 ELSE 0 END), 0) AS downvotes
        FROM community_votes
        WHERE target_type = ? AND target_id = ?
        """,
        (str(target_type), str(target_id)),
    ).fetchone()
    up = int((row["upvotes"] or 0) if row else 0)
    down = int((row["downvotes"] or 0) if row else 0)

    table = "community_posts" if str(target_type) == "post" else "community_comments"
    conn.execute(
        f"UPDATE {table} SET upvotes = ?, downvotes = ?, updated_at = ? WHERE id = ?",
        (up, down, int(time.time()), str(target_id)),
    )


def set_community_vote(
    vote_id: str,
    *,
    user_id: str,
    target_type: str,
    target_id: str,
    vote: int,
) -> Dict[str, int]:
    if vote not in (-1, 0, 1):
        raise ValueError("vote must be -1/0/1")
    now = int(time.time())
    conn = get_conn()
    try:
        existing = conn.execute(
            """
            SELECT id FROM community_votes
            WHERE user_id = ? AND target_type = ? AND target_id = ?
            """,
            (str(user_id), str(target_type), str(target_id)),
        ).fetchone()
        if vote == 0:
            if existing:
                conn.execute("DELETE FROM community_votes WHERE id = ?", (str(existing["id"]),))
        else:
            if existing:
                conn.execute(
                    "UPDATE community_votes SET vote = ?, updated_at = ? WHERE id = ?",
                    (int(vote), now, str(existing["id"])),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO community_votes (id, user_id, target_type, target_id, vote, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(vote_id),
                        str(user_id),
                        str(target_type),
                        str(target_id),
                        int(vote),
                        now,
                        now,
                    ),
                )
        _refresh_vote_totals(conn, str(target_type), str(target_id))
        conn.commit()

        row = conn.execute(
            "SELECT upvotes, downvotes FROM community_posts WHERE id = ?" if str(target_type) == "post"
            else "SELECT upvotes, downvotes FROM community_comments WHERE id = ?",
            (str(target_id),),
        ).fetchone()
        return {"upvotes": int((row["upvotes"] or 0) if row else 0), "downvotes": int((row["downvotes"] or 0) if row else 0)}
    finally:
        conn.close()


def get_user_community_summary(user_id: str) -> Dict[str, int]:
    conn = get_conn()
    try:
        posts = conn.execute(
            "SELECT COUNT(*) AS cnt FROM community_posts WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
        comments = conn.execute(
            "SELECT COUNT(*) AS cnt FROM community_comments WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
        votes = conn.execute(
            "SELECT COUNT(*) AS cnt FROM community_votes WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
        return {
            "post_count": int((posts["cnt"] or 0) if posts else 0),
            "comment_count": int((comments["cnt"] or 0) if comments else 0),
            "vote_count": int((votes["cnt"] or 0) if votes else 0),
        }
    finally:
        conn.close()


def create_study_group(
    group_id: str,
    *,
    owner_user_id: str,
    name: str,
    description: str = "",
    is_public: bool = True,
    max_members: int = 20,
) -> None:
    now = int(time.time())
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO study_groups (
              id, owner_user_id, name, description, is_public, max_members, member_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                str(group_id),
                str(owner_user_id),
                str(name),
                str(description or ""),
                1 if is_public else 0,
                max(2, int(max_members)),
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO study_group_members (
              id, group_id, user_id, role, joined_at, last_checkin_at, checkin_streak, total_checkins
            ) VALUES (?, ?, ?, 'owner', ?, 0, 0, 0)
            """,
            (str(uuid4()), str(group_id), str(owner_user_id), now),
        )
        conn.commit()
    finally:
        conn.close()


def get_study_group(group_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM study_groups WHERE id = ?", (str(group_id),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_study_groups(public_only: bool = True, limit: int = 30, offset: int = 0) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        if public_only:
            cur = conn.execute(
                """
                SELECT *
                FROM study_groups
                WHERE is_public = 1
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (max(1, int(limit)), max(0, int(offset))),
            )
        else:
            cur = conn.execute(
                """
                SELECT *
                FROM study_groups
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (max(1, int(limit)), max(0, int(offset))),
            )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def list_user_study_groups(user_id: str, limit: int = 30) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT g.*, m.role, m.joined_at, m.last_checkin_at, m.checkin_streak, m.total_checkins
            FROM study_group_members m
            JOIN study_groups g ON g.id = m.group_id
            WHERE m.user_id = ?
            ORDER BY m.joined_at DESC
            LIMIT ?
            """,
            (str(user_id), max(1, int(limit))),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def get_study_group_member(group_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM study_group_members WHERE group_id = ? AND user_id = ?",
            (str(group_id), str(user_id)),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def join_study_group(group_id: str, user_id: str, role: str = "member") -> Dict[str, Any]:
    now = int(time.time())
    conn = get_conn()
    try:
        group = conn.execute("SELECT * FROM study_groups WHERE id = ?", (str(group_id),)).fetchone()
        if not group:
            raise ValueError("group_not_found")
        if int(group["member_count"] or 0) >= int(group["max_members"] or 0):
            raise ValueError("group_full")

        existing = conn.execute(
            "SELECT * FROM study_group_members WHERE group_id = ? AND user_id = ?",
            (str(group_id), str(user_id)),
        ).fetchone()
        if existing:
            return dict(existing)

        conn.execute(
            """
            INSERT INTO study_group_members (
              id, group_id, user_id, role, joined_at, last_checkin_at, checkin_streak, total_checkins
            ) VALUES (?, ?, ?, ?, ?, 0, 0, 0)
            """,
            (str(uuid4()), str(group_id), str(user_id), str(role), now),
        )
        conn.execute(
            "UPDATE study_groups SET member_count = member_count + 1, updated_at = ? WHERE id = ?",
            (now, str(group_id)),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM study_group_members WHERE group_id = ? AND user_id = ?",
            (str(group_id), str(user_id)),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def create_study_group_checkin(
    checkin_id: str,
    *,
    group_id: str,
    user_id: str,
    note: str = "",
    score: int = 1,
) -> Dict[str, Any]:
    now = int(time.time())
    day_start = int(now // 86400) * 86400
    conn = get_conn()
    try:
        member = conn.execute(
            "SELECT * FROM study_group_members WHERE group_id = ? AND user_id = ?",
            (str(group_id), str(user_id)),
        ).fetchone()
        if not member:
            raise ValueError("not_member")

        existing_today = conn.execute(
            """
            SELECT * FROM study_group_checkins
            WHERE group_id = ? AND user_id = ? AND created_at >= ? AND created_at < ?
            LIMIT 1
            """,
            (str(group_id), str(user_id), day_start, day_start + 86400),
        ).fetchone()
        if existing_today:
            return dict(existing_today)

        conn.execute(
            """
            INSERT INTO study_group_checkins (id, group_id, user_id, note, score, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(checkin_id), str(group_id), str(user_id), str(note or ""), max(1, int(score)), now),
        )

        last_checkin_at = int(member["last_checkin_at"] or 0)
        prev_day_start = int(last_checkin_at // 86400) * 86400 if last_checkin_at > 0 else 0
        streak = int(member["checkin_streak"] or 0)
        if prev_day_start == day_start - 86400:
            streak += 1
        elif prev_day_start == day_start:
            streak = streak
        else:
            streak = 1

        conn.execute(
            """
            UPDATE study_group_members
            SET last_checkin_at = ?, checkin_streak = ?, total_checkins = total_checkins + 1
            WHERE group_id = ? AND user_id = ?
            """,
            (now, streak, str(group_id), str(user_id)),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM study_group_checkins WHERE id = ?",
            (str(checkin_id),),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def list_study_group_checkins(group_id: str, limit: int = 100) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM study_group_checkins
            WHERE group_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(group_id), max(1, int(limit))),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def list_study_group_leaderboard(group_id: str, limit: int = 20) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT user_id, role, checkin_streak, total_checkins, last_checkin_at
            FROM study_group_members
            WHERE group_id = ?
            ORDER BY total_checkins DESC, checkin_streak DESC, last_checkin_at DESC
            LIMIT ?
            """,
            (str(group_id), max(1, int(limit))),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def create_payment_order(
    order_id: str,
    *,
    user_id: str,
    product_code: str,
    product_name: str,
    quantity: int,
    unit_price_cents: int,
    total_price_cents: int,
    currency: str = "CNY",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    now = int(time.time())
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO payment_orders (
              id, user_id, product_code, product_name, quantity,
              unit_price_cents, total_price_cents, currency, status, metadata,
              created_at, updated_at, paid_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, NULL)
            """,
            (
                str(order_id),
                str(user_id),
                str(product_code),
                str(product_name),
                max(1, int(quantity)),
                int(unit_price_cents),
                int(total_price_cents),
                str(currency or "CNY"),
                json.dumps(metadata or {}),
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_payment_order(order_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM payment_orders WHERE id = ?", (str(order_id),)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["metadata"] = json.loads(item["metadata"]) if item.get("metadata") else {}
        return item
    finally:
        conn.close()


def list_user_payment_orders(user_id: str, limit: int = 30) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM payment_orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(user_id), max(1, int(limit))),
        )
        rows: list[Dict[str, Any]] = []
        for row in cur.fetchall():
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"]) if item.get("metadata") else {}
            rows.append(item)
        return rows
    finally:
        conn.close()


def update_payment_order_status(order_id: str, status: str, paid_at: Optional[int] = None) -> None:
    now = int(time.time())
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE payment_orders SET status = ?, updated_at = ?, paid_at = COALESCE(?, paid_at) WHERE id = ?",
            (str(status), now, int(paid_at) if paid_at else None, str(order_id)),
        )
        conn.commit()
    finally:
        conn.close()


def create_payment_transaction(
    transaction_id: str,
    *,
    order_id: str,
    user_id: str,
    provider: str,
    provider_txn_id: str,
    amount_cents: int,
    status: str = "pending",
    raw_payload: Optional[Dict[str, Any]] = None,
) -> bool:
    now = int(time.time())
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO payment_transactions (
              id, order_id, user_id, provider, provider_txn_id,
              amount_cents, status, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(transaction_id),
                str(order_id),
                str(user_id),
                str(provider),
                str(provider_txn_id),
                int(amount_cents),
                str(status),
                json.dumps(raw_payload or {}),
                now,
                now,
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def upsert_user_entitlement(
    *,
    user_id: str,
    feature_code: str,
    delta: int,
    source_type: str,
    source_id: str,
    note: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    now = int(time.time())
    delta = int(delta)
    if delta == 0:
        return True
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        dup = conn.execute(
            """
            SELECT id FROM entitlement_ledger
            WHERE user_id = ? AND feature_code = ? AND source_type = ? AND source_id = ?
            LIMIT 1
            """,
            (str(user_id), str(feature_code), str(source_type), str(source_id)),
        ).fetchone()
        if dup:
            conn.rollback()
            return False

        row = conn.execute(
            """
            SELECT *
            FROM user_entitlements
            WHERE user_id = ? AND feature_code = ?
            """,
            (str(user_id), str(feature_code)),
        ).fetchone()
        if not row:
            eid = str(uuid4())
            balance = max(0, delta)
            granted = max(0, delta)
            consumed = max(0, -delta)
            conn.execute(
                """
                INSERT INTO user_entitlements (
                  id, user_id, feature_code, balance, total_granted, total_consumed, updated_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (eid, str(user_id), str(feature_code), balance, granted, consumed, now, now),
            )
            new_balance = balance
        else:
            balance = int(row["balance"] or 0)
            new_balance = balance + delta
            if new_balance < 0:
                conn.rollback()
                raise ValueError("insufficient_entitlement")
            total_granted = int(row["total_granted"] or 0) + max(0, delta)
            total_consumed = int(row["total_consumed"] or 0) + max(0, -delta)
            conn.execute(
                """
                UPDATE user_entitlements
                SET balance = ?, total_granted = ?, total_consumed = ?, updated_at = ?
                WHERE user_id = ? AND feature_code = ?
                """,
                (new_balance, total_granted, total_consumed, now, str(user_id), str(feature_code)),
            )

        conn.execute(
            """
            INSERT INTO entitlement_ledger (
              id, user_id, feature_code, change_amount, balance_after,
              source_type, source_id, note, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                str(user_id),
                str(feature_code),
                delta,
                new_balance,
                str(source_type),
                str(source_id),
                str(note or ""),
                json.dumps(metadata or {}),
                now,
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def consume_user_entitlement(
    *,
    user_id: str,
    feature_code: str,
    amount: int,
    source_type: str,
    source_id: str,
    note: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    try:
        return upsert_user_entitlement(
            user_id=user_id,
            feature_code=feature_code,
            delta=-abs(int(amount)),
            source_type=source_type,
            source_id=source_id,
            note=note,
            metadata=metadata,
        )
    except ValueError:
        return False


def get_user_entitlement_balance(user_id: str, feature_code: str) -> Optional[int]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT balance FROM user_entitlements WHERE user_id = ? AND feature_code = ?",
            (str(user_id), str(feature_code)),
        ).fetchone()
        if not row:
            return None
        return int(row["balance"] or 0)
    finally:
        conn.close()


def list_user_entitlements(user_id: str) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM user_entitlements
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (str(user_id),),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def is_admin_user(user_id: str, username: str = "") -> bool:
    env_admins = {
        x.strip().lower()
        for x in str(os.environ.get("ADMIN_USERNAMES", "admin,demo")).split(",")
        if x.strip()
    }
    if str(username or "").strip().lower() in env_admins:
        return True
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM admin_users WHERE user_id = ? LIMIT 1",
            (str(user_id),),
        ).fetchone()
        return bool(row)
    finally:
        conn.close()


def create_admin_audit_log(
    log_id: str,
    *,
    admin_user_id: str,
    action: str,
    target_type: str,
    target_id: str,
    detail: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO admin_audit_logs (
              id, admin_user_id, action, target_type, target_id, detail, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(log_id),
                str(admin_user_id),
                str(action),
                str(target_type),
                str(target_id),
                str(detail or ""),
                json.dumps(metadata or {}),
                int(time.time()),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_admin_overview_metrics() -> Dict[str, Any]:
    conn = get_conn()
    try:
        users = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        active_users = conn.execute(
            """
            SELECT COUNT(DISTINCT user_id) AS cnt
            FROM user_activities
            WHERE created_at >= ?
            """,
            (int(time.time()) - 7 * 86400,),
        ).fetchone()
        orders = conn.execute(
            """
            SELECT
              COUNT(*) AS total_orders,
              COALESCE(SUM(CASE WHEN status = 'paid' THEN total_price_cents ELSE 0 END), 0) AS paid_amount_cents,
              COALESCE(SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END), 0) AS paid_orders
            FROM payment_orders
            """
        ).fetchone()
        pending_posts = conn.execute(
            "SELECT COUNT(*) AS cnt FROM community_posts WHERE status = 'pending_review'"
        ).fetchone()
        pending_comments = conn.execute(
            "SELECT COUNT(*) AS cnt FROM community_comments WHERE status = 'pending_review'"
        ).fetchone()
        writing_ent = conn.execute(
            """
            SELECT
              COALESCE(SUM(balance), 0) AS balance_sum,
              COALESCE(SUM(total_granted), 0) AS granted_sum,
              COALESCE(SUM(total_consumed), 0) AS consumed_sum
            FROM user_entitlements
            WHERE feature_code = 'writing_ai_review'
            """
        ).fetchone()
        return {
            "total_users": int((users["cnt"] or 0) if users else 0),
            "active_users_7d": int((active_users["cnt"] or 0) if active_users else 0),
            "total_orders": int((orders["total_orders"] or 0) if orders else 0),
            "paid_orders": int((orders["paid_orders"] or 0) if orders else 0),
            "paid_amount_cents": int((orders["paid_amount_cents"] or 0) if orders else 0),
            "pending_posts": int((pending_posts["cnt"] or 0) if pending_posts else 0),
            "pending_comments": int((pending_comments["cnt"] or 0) if pending_comments else 0),
            "writing_ai_review_balance_sum": int((writing_ent["balance_sum"] or 0) if writing_ent else 0),
            "writing_ai_review_granted_sum": int((writing_ent["granted_sum"] or 0) if writing_ent else 0),
            "writing_ai_review_consumed_sum": int((writing_ent["consumed_sum"] or 0) if writing_ent else 0),
        }
    finally:
        conn.close()


def list_pending_community_posts(limit: int = 50) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM community_posts
            WHERE status = 'pending_review'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        )
        rows: list[Dict[str, Any]] = []
        for row in cur.fetchall():
            item = dict(row)
            item["tags"] = json.loads(item["tags"]) if item.get("tags") else []
            rows.append(item)
        return rows
    finally:
        conn.close()


def list_pending_community_comments(limit: int = 100) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT c.*, p.title AS post_title
            FROM community_comments c
            LEFT JOIN community_posts p ON p.id = c.post_id
            WHERE c.status = 'pending_review'
            ORDER BY c.created_at ASC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def moderate_community_post(post_id: str, status: str) -> bool:
    now = int(time.time())
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE community_posts SET status = ?, updated_at = ? WHERE id = ?",
            (str(status), now, str(post_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def moderate_community_comment(comment_id: str, status: str) -> bool:
    now = int(time.time())
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE community_comments SET status = ?, updated_at = ? WHERE id = ?",
            (str(status), now, str(comment_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_payment_orders_admin(status: str = "", user_id: str = "", limit: int = 100) -> list[Dict[str, Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if str(status).strip():
        where.append("status = ?")
        params.append(str(status).strip())
    if str(user_id).strip():
        where.append("user_id = ?")
        params.append(str(user_id).strip())
    params.append(max(1, int(limit)))
    conn = get_conn()
    try:
        cur = conn.execute(
            f"""
            SELECT *
            FROM payment_orders
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        )
        rows: list[Dict[str, Any]] = []
        for row in cur.fetchall():
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"]) if item.get("metadata") else {}
            rows.append(item)
        return rows
    finally:
        conn.close()


def list_entitlement_ledger_admin(
    *,
    user_id: str = "",
    feature_code: str = "",
    limit: int = 200,
) -> list[Dict[str, Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if str(user_id).strip():
        where.append("user_id = ?")
        params.append(str(user_id).strip())
    if str(feature_code).strip():
        where.append("feature_code = ?")
        params.append(str(feature_code).strip())
    params.append(max(1, int(limit)))
    conn = get_conn()
    try:
        cur = conn.execute(
            f"""
            SELECT *
            FROM entitlement_ledger
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        )
        rows: list[Dict[str, Any]] = []
        for row in cur.fetchall():
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"]) if item.get("metadata") else {}
            rows.append(item)
        return rows
    finally:
        conn.close()


def create_growth_campaign(
    campaign_id: str,
    *,
    created_by: str,
    title: str,
    description: str,
    campaign_type: str,
    status: str,
    start_at: int,
    end_at: int,
    reward_points: int,
    rules: Optional[Dict[str, Any]] = None,
) -> None:
    now = int(time.time())
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO growth_campaigns (
              id, created_by, title, description, campaign_type, status,
              start_at, end_at, reward_points, rules_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(campaign_id),
                str(created_by),
                str(title),
                str(description or ""),
                str(campaign_type),
                str(status),
                int(start_at),
                int(end_at),
                max(0, int(reward_points)),
                json.dumps(rules or {}),
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_growth_campaign_status(campaign_id: str, status: str) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE growth_campaigns SET status = ?, updated_at = ? WHERE id = ?",
            (str(status), int(time.time()), str(campaign_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_growth_campaign(campaign_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM growth_campaigns WHERE id = ?", (str(campaign_id),)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["rules_json"] = json.loads(item["rules_json"]) if item.get("rules_json") else {}
        return item
    finally:
        conn.close()


def list_growth_campaigns(status: str = "", limit: int = 50) -> list[Dict[str, Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if str(status).strip():
        where.append("status = ?")
        params.append(str(status).strip())
    params.append(max(1, int(limit)))
    conn = get_conn()
    try:
        cur = conn.execute(
            f"""
            SELECT *
            FROM growth_campaigns
            WHERE {' AND '.join(where)}
            ORDER BY start_at DESC, created_at DESC
            LIMIT ?
            """,
            params,
        )
        rows: list[Dict[str, Any]] = []
        for row in cur.fetchall():
            item = dict(row)
            item["rules_json"] = json.loads(item["rules_json"]) if item.get("rules_json") else {}
            rows.append(item)
        return rows
    finally:
        conn.close()


def join_growth_campaign(campaign_id: str, user_id: str, target: int = 1) -> Dict[str, Any]:
    now = int(time.time())
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM growth_campaign_participants
            WHERE campaign_id = ? AND user_id = ?
            """,
            (str(campaign_id), str(user_id)),
        ).fetchone()
        if row:
            return dict(row)

        pid = str(uuid4())
        conn.execute(
            """
            INSERT INTO growth_campaign_participants (
              id, campaign_id, user_id, status, progress, target, joined_at, updated_at, completed_at
            ) VALUES (?, ?, ?, 'joined', 0, ?, ?, ?, NULL)
            """,
            (pid, str(campaign_id), str(user_id), max(1, int(target)), now, now),
        )
        conn.commit()
        created = conn.execute(
            """
            SELECT *
            FROM growth_campaign_participants
            WHERE id = ?
            """,
            (pid,),
        ).fetchone()
        return dict(created) if created else {}
    finally:
        conn.close()


def get_growth_campaign_participant(campaign_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM growth_campaign_participants
            WHERE campaign_id = ? AND user_id = ?
            """,
            (str(campaign_id), str(user_id)),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_growth_campaign_event(
    event_id: str,
    *,
    campaign_id: str,
    user_id: str,
    event_type: str,
    value: int = 1,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO growth_campaign_events (
              id, campaign_id, user_id, event_type, value, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(event_id),
                str(campaign_id),
                str(user_id),
                str(event_type),
                max(1, int(value)),
                json.dumps(metadata or {}),
                int(time.time()),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def advance_growth_campaign_progress(
    *,
    campaign_id: str,
    user_id: str,
    delta: int = 1,
) -> Dict[str, Any]:
    now = int(time.time())
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM growth_campaign_participants
            WHERE campaign_id = ? AND user_id = ?
            """,
            (str(campaign_id), str(user_id)),
        ).fetchone()
        if not row:
            raise ValueError("participant_not_found")
        progress = int(row["progress"] or 0) + max(1, int(delta))
        target = max(1, int(row["target"] or 1))
        status = "completed" if progress >= target else str(row["status"] or "joined")
        completed_at = now if status == "completed" else row["completed_at"]
        conn.execute(
            """
            UPDATE growth_campaign_participants
            SET progress = ?, status = ?, updated_at = ?, completed_at = ?
            WHERE campaign_id = ? AND user_id = ?
            """,
            (progress, status, now, completed_at, str(campaign_id), str(user_id)),
        )
        conn.commit()
        updated = conn.execute(
            """
            SELECT *
            FROM growth_campaign_participants
            WHERE campaign_id = ? AND user_id = ?
            """,
            (str(campaign_id), str(user_id)),
        ).fetchone()
        return dict(updated) if updated else {}
    finally:
        conn.close()


def list_growth_campaign_participants(campaign_id: str, limit: int = 200) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM growth_campaign_participants
            WHERE campaign_id = ?
            ORDER BY progress DESC, updated_at DESC
            LIMIT ?
            """,
            (str(campaign_id), max(1, int(limit))),
        )
        return [dict(x) for x in cur.fetchall()]
    finally:
        conn.close()


def get_growth_campaign_stats(campaign_id: str) -> Dict[str, Any]:
    conn = get_conn()
    try:
        total = conn.execute(
            "SELECT COUNT(*) AS cnt FROM growth_campaign_participants WHERE campaign_id = ?",
            (str(campaign_id),),
        ).fetchone()
        completed = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM growth_campaign_participants
            WHERE campaign_id = ? AND status = 'completed'
            """,
            (str(campaign_id),),
        ).fetchone()
        events = conn.execute(
            """
            SELECT
              COUNT(*) AS event_count,
              COALESCE(SUM(value), 0) AS total_value
            FROM growth_campaign_events
            WHERE campaign_id = ?
            """,
            (str(campaign_id),),
        ).fetchone()
        participant_total = int((total["cnt"] or 0) if total else 0)
        completed_total = int((completed["cnt"] or 0) if completed else 0)
        rate = (completed_total / participant_total * 100.0) if participant_total > 0 else 0.0
        return {
            "participant_count": participant_total,
            "completed_count": completed_total,
            "completion_rate": round(rate, 2),
            "event_count": int((events["event_count"] or 0) if events else 0),
            "event_value_total": int((events["total_value"] or 0) if events else 0),
        }
    finally:
        conn.close()


# Reminder DAO
def create_reminder(reminder_id: str, user_id: str, reminder_data: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO reminders (
              id, user_id, type, title, content, scheduled_at, 
              status, channel, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reminder_id,
                user_id,
                reminder_data.get('type', 'task'),
                reminder_data.get('title', ''),
                reminder_data.get('content', ''),
                reminder_data.get('scheduled_at', int(time.time())),
                reminder_data.get('status', 'pending'),
                reminder_data.get('channel', 'app'),
                json.dumps(reminder_data.get('metadata', {})),
                int(time.time())
            )
        )
        conn.commit()
    finally:
        conn.close()


def has_recent_reminder(
    user_id: str,
    reminder_type: str,
    source: str,
    lookback_seconds: int = 24 * 3600,
    status_scope: Optional[list[str]] = None,
) -> bool:
    conn = get_conn()
    try:
        now = int(time.time())
        since = now - max(0, int(lookback_seconds))
        statuses = status_scope or ["pending", "sent"]
        placeholders = ",".join("?" for _ in statuses)
        cur = conn.execute(
            f"""
            SELECT metadata FROM reminders
            WHERE user_id = ?
              AND type = ?
              AND created_at >= ?
              AND status IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (str(user_id), reminder_type, since, *statuses),
        )
        for row in cur.fetchall():
            raw = row["metadata"]
            if not raw:
                continue
            try:
                metadata = json.loads(raw)
            except Exception:
                continue
            if str(metadata.get("source", "")) == str(source):
                return True
        return False
    finally:
        conn.close()


def get_reminder(reminder_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        row = cur.fetchone()
        if not row:
            return None
        reminder = dict(row)
        reminder['metadata'] = json.loads(reminder['metadata']) if reminder['metadata'] else {}
        return reminder
    finally:
        conn.close()


def get_user_reminders(user_id: str, status: Optional[str] = None) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        if status:
            cur = conn.execute(
                "SELECT * FROM reminders WHERE user_id = ? AND status = ? ORDER BY scheduled_at ASC",
                (user_id, status)
            )
        else:
            cur = conn.execute(
                "SELECT * FROM reminders WHERE user_id = ? ORDER BY scheduled_at ASC",
                (user_id,)
            )
        reminders = []
        for row in cur.fetchall():
            reminder = dict(row)
            reminder['metadata'] = json.loads(reminder['metadata']) if reminder['metadata'] else {}
            reminders.append(reminder)
        return reminders
    finally:
        conn.close()


def get_pending_reminders() -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(time.time())
        cur = conn.execute(
            "SELECT * FROM reminders WHERE status = 'pending' AND scheduled_at <= ? ORDER BY scheduled_at ASC",
            (now,)
        )
        reminders = []
        for row in cur.fetchall():
            reminder = dict(row)
            reminder['metadata'] = json.loads(reminder['metadata']) if reminder['metadata'] else {}
            reminders.append(reminder)
        return reminders
    finally:
        conn.close()


def update_reminder_status(reminder_id: str, status: str, sent_at: Optional[int] = None) -> None:
    conn = get_conn()
    try:
        if sent_at:
            conn.execute(
                "UPDATE reminders SET status = ?, sent_at = ? WHERE id = ?",
                (status, sent_at, reminder_id)
            )
        else:
            conn.execute(
                "UPDATE reminders SET status = ? WHERE id = ?",
                (status, reminder_id)
            )
        conn.commit()
    finally:
        conn.close()


def update_reminder_metadata(reminder_id: str, metadata: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE reminders SET metadata = ? WHERE id = ?",
            (json.dumps(metadata), reminder_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_reminder_retry(
    reminder_id: str,
    error_message: str,
    max_retries: int = 3,
    retry_delay_seconds: int = 300,
) -> Dict[str, Any]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT metadata FROM reminders WHERE id = ?", (reminder_id,))
        row = cur.fetchone()
        if not row:
            return {"updated": False, "status": "not_found", "retry_count": 0}

        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        retry_count = int(metadata.get("retry_count", 0)) + 1
        metadata["retry_count"] = retry_count
        metadata["last_error"] = str(error_message or "unknown_error")
        metadata["last_attempt_at"] = int(time.time())

        if retry_count > max_retries:
            conn.execute(
                "UPDATE reminders SET status = ?, metadata = ? WHERE id = ?",
                ("failed", json.dumps(metadata), reminder_id),
            )
            conn.commit()
            return {"updated": True, "status": "failed", "retry_count": retry_count}

        next_time = int(time.time()) + max(1, int(retry_delay_seconds))
        conn.execute(
            "UPDATE reminders SET status = ?, scheduled_at = ?, metadata = ? WHERE id = ?",
            ("pending", next_time, json.dumps(metadata), reminder_id),
        )
        conn.commit()
        return {"updated": True, "status": "pending", "retry_count": retry_count, "next_scheduled_at": next_time}
    finally:
        conn.close()


def delete_reminder(reminder_id: str) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        conn.commit()
    finally:
        conn.close()


# Reminder Preferences DAO
def get_reminder_preferences(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM reminder_preferences WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        preferences = dict(row)
        preferences['channels'] = json.loads(preferences['channels']) if preferences['channels'] else []
        preferences['preferred_times'] = json.loads(preferences['preferred_times']) if preferences['preferred_times'] else []
        preferences['quiet_hours'] = json.loads(preferences['quiet_hours']) if preferences['quiet_hours'] else {}
        return preferences
    finally:
        conn.close()


def set_reminder_preferences(user_id: str, preferences: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        # 检查是否存在
        existing = get_reminder_preferences(user_id)
        now = int(time.time())
        
        if existing:
            # 更新
            conn.execute(
                """
                UPDATE reminder_preferences 
                SET enabled = ?, channels = ?, preferred_times = ?, 
                    quiet_hours = ?, updated_at = ? 
                WHERE user_id = ?
                """,
                (
                    preferences.get('enabled', 1),
                    json.dumps(preferences.get('channels', ['app'])),
                    json.dumps(preferences.get('preferred_times', [])),
                    json.dumps(preferences.get('quiet_hours', {})),
                    now,
                    user_id
                )
            )
        else:
            # 插入
            conn.execute(
                """
                INSERT INTO reminder_preferences (
                  user_id, enabled, channels, preferred_times, 
                  quiet_hours, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    preferences.get('enabled', 1),
                    json.dumps(preferences.get('channels', ['app'])),
                    json.dumps(preferences.get('preferred_times', [])),
                    json.dumps(preferences.get('quiet_hours', {})),
                    now,
                    now
                )
            )
        conn.commit()
    finally:
        conn.close()


# Learning Events DAO
def save_learning_event(event_id: str, user_id: str, event_data: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO learning_events (
              event_id, user_id, event_type, event_name, 
              properties, timestamp, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                user_id,
                event_data.get('event_type', ''),
                event_data.get('event_name', ''),
                json.dumps(event_data.get('properties', {})),
                event_data.get('timestamp', int(time.time())),
                int(time.time())
            )
        )
        conn.commit()
    finally:
        conn.close()


def get_user_events(user_id: str, limit: int = 100, offset: int = 0) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM learning_events WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset)
        )
        events = []
        for row in cur.fetchall():
            event = dict(row)
            event['properties'] = json.loads(event['properties']) if event['properties'] else {}
            events.append(event)
        return events
    finally:
        conn.close()


def get_event_stats(user_id: str, time_range: int = 86400) -> Dict[str, Any]:
    conn = get_conn()
    try:
        cutoff_time = int(time.time()) - time_range
        cur = conn.execute(
            "SELECT event_type, COUNT(*) as count FROM learning_events WHERE user_id = ? AND timestamp >= ? GROUP BY event_type",
            (user_id, cutoff_time)
        )
        
        event_counts = {}
        total_events = 0
        for row in cur.fetchall():
            event_counts[row['event_type']] = row['count']
            total_events += row['count']
        
        # 计算活跃天数
        cur2 = conn.execute(
            "SELECT COUNT(DISTINCT DATE(timestamp, 'unixepoch')) as active_days FROM learning_events WHERE user_id = ? AND timestamp >= ?",
            (user_id, cutoff_time)
        )
        active_days_row = cur2.fetchone()
        active_days = active_days_row['active_days'] if active_days_row else 0
        
        return {
            'total_events': total_events,
            'event_counts': event_counts,
            'active_days': active_days,
            'time_range': time_range
        }
    finally:
        conn.close()


# User Activities DAO
def save_user_activity(activity_id: str, user_id: str, activity_data: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO user_activities (
              id, user_id, activity_type, module, 
              duration, score, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                activity_id,
                user_id,
                activity_data.get('activity_type', 'general'),
                activity_data.get('module', 'general'),
                activity_data.get('duration', 0),
                activity_data.get('score', 0.0),
                json.dumps(activity_data.get('metadata', {})),
                int(time.time()),
                int(time.time())
            )
        )
        conn.commit()
    finally:
        conn.close()


def get_user_activities(user_id: str, limit: int = 50, offset: int = 0) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM user_activities WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset)
        )
        activities = []
        for row in cur.fetchall():
            activity = dict(row)
            activity['metadata'] = json.loads(activity['metadata']) if activity['metadata'] else {}
            activities.append(activity)
        return activities
    finally:
        conn.close()


def get_activity_stats(user_id: str, time_range: int = 86400) -> Dict[str, Any]:
    conn = get_conn()
    try:
        cutoff_time = int(time.time()) - time_range
        
        # 计算总学习时长
        cur = conn.execute(
            "SELECT SUM(duration) as total_duration, AVG(duration) as avg_duration FROM user_activities WHERE user_id = ? AND created_at >= ?",
            (user_id, cutoff_time)
        )
        duration_row = cur.fetchone()
        total_duration = duration_row['total_duration'] or 0
        avg_duration = duration_row['avg_duration'] or 0
        
        # 计算总活动数
        cur2 = conn.execute(
            "SELECT COUNT(*) as total_activities FROM user_activities WHERE user_id = ? AND created_at >= ?",
            (user_id, cutoff_time)
        )
        activity_count_row = cur2.fetchone()
        total_activities = activity_count_row['total_activities'] or 0
        
        # 计算平均分
        cur3 = conn.execute(
            "SELECT AVG(score) as avg_score FROM user_activities WHERE user_id = ? AND created_at >= ? AND score > 0",
            (user_id, cutoff_time)
        )
        score_row = cur3.fetchone()
        avg_score = score_row['avg_score'] or 0
        
        return {
            'total_duration': total_duration,
            'average_duration': avg_duration,
            'total_activities': total_activities,
            'average_score': avg_score,
            'time_range': time_range
        }
    finally:
        conn.close()


def get_recent_learning_sessions(user_id: str, days: int = 14, limit: int = 200) -> list[Dict[str, Any]]:
    """
    获取最近学习会话（用于智能提醒），优先来自 user_activities，补充 learning_events。
    """
    conn = get_conn()
    try:
        cutoff_time = int(time.time()) - max(1, int(days)) * 24 * 3600
        max_limit = max(1, min(int(limit), 1000))

        sessions: list[Dict[str, Any]] = []
        cur = conn.execute(
            """
            SELECT id, activity_type, module, duration, created_at
            FROM user_activities
            WHERE user_id = ? AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, cutoff_time, max_limit),
        )
        for row in cur.fetchall():
            sessions.append(
                {
                    "id": str(row["id"]),
                    "user_id": user_id,
                    "type": str(row["module"] or row["activity_type"] or "general"),
                    "duration": int(row["duration"] or 0),
                    "created_at": int(row["created_at"] or 0),
                    "completed": True,
                }
            )

        if len(sessions) < max_limit:
            remain = max_limit - len(sessions)
            cur2 = conn.execute(
                """
                SELECT event_id, event_type, event_name, properties, timestamp
                FROM learning_events
                WHERE user_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (user_id, cutoff_time, remain),
            )
            for row in cur2.fetchall():
                props = json.loads(row["properties"]) if row["properties"] else {}
                sessions.append(
                    {
                        "id": str(row["event_id"]),
                        "user_id": user_id,
                        "type": str(row["event_name"] or row["event_type"] or "general"),
                        "duration": int(props.get("duration", 0) or 0),
                        "created_at": int(row["timestamp"] or 0),
                        "completed": True,
                    }
                )

        sessions.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
        return sessions[:max_limit]
    finally:
        conn.close()


def get_last_reminder_time(user_id: str) -> Optional[int]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT MAX(COALESCE(sent_at, created_at)) AS last_ts
            FROM reminders
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        value = row["last_ts"]
        return int(value) if value is not None else None
    finally:
        conn.close()


# Mistake DAO
def save_mistake(mistake_id: str, user_id: str, mistake_data: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO mistakes (
              id, user_id, module, question_id, question_type, error_type, 
              content, user_answer, correct_answer, explanation, difficulty, 
              tags, created_at, last_reviewed_at, next_review_date, mastery_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mistake_id,
                user_id,
                mistake_data.get('module', ''),
                mistake_data.get('question_id', ''),
                mistake_data.get('question_type', ''),
                mistake_data.get('error_type', ''),
                mistake_data.get('content', ''),
                mistake_data.get('user_answer', ''),
                mistake_data.get('correct_answer', ''),
                mistake_data.get('explanation', ''),
                mistake_data.get('difficulty', 'medium'),
                json.dumps(mistake_data.get('tags', [])),
                int(time.time()),
                int(time.time()),
                int(time.time()) + 24 * 3600,  # 1 day later
                mistake_data.get('mastery_level', 0.0)
            )
        )
        conn.commit()
    finally:
        conn.close()


def get_user_mistakes(
    user_id: str,
    module: Optional[str] = None,
    limit: int = 50,
    question_type: Optional[str] = None,
    error_type: Optional[str] = None,
    created_from: Optional[int] = None,
    created_to: Optional[int] = None,
    next_review_from: Optional[int] = None,
    next_review_to: Optional[int] = None,
) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        conditions = ["user_id = ?"]
        params: list[Any] = [user_id]
        if module:
            conditions.append("module = ?")
            params.append(module)
        if question_type:
            conditions.append("question_type = ?")
            params.append(question_type)
        if error_type:
            conditions.append("error_type = ?")
            params.append(error_type)
        if created_from is not None:
            conditions.append("created_at >= ?")
            params.append(int(created_from))
        if created_to is not None:
            conditions.append("created_at <= ?")
            params.append(int(created_to))
        if next_review_from is not None:
            conditions.append("next_review_date >= ?")
            params.append(int(next_review_from))
        if next_review_to is not None:
            conditions.append("next_review_date <= ?")
            params.append(int(next_review_to))
        where_clause = " AND ".join(conditions)
        cur = conn.execute(
            f"SELECT * FROM mistakes WHERE {where_clause} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        )
        mistakes = []
        for row in cur.fetchall():
            mistake = dict(row)
            mistake['tags'] = json.loads(mistake['tags']) if mistake['tags'] else []
            mistakes.append(mistake)
        return mistakes
    finally:
        conn.close()


def get_due_mistakes(
    user_id: str,
    module: Optional[str] = None,
    limit: int = 50,
    now_ts: Optional[int] = None,
    question_type: Optional[str] = None,
) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        if module and question_type:
            cur = conn.execute(
                """
                SELECT * FROM mistakes
                WHERE user_id = ? AND module = ? AND question_type = ? AND next_review_date <= ?
                ORDER BY next_review_date ASC, created_at ASC
                LIMIT ?
                """,
                (user_id, module, question_type, now, limit),
            )
        elif module:
            cur = conn.execute(
                """
                SELECT * FROM mistakes
                WHERE user_id = ? AND module = ? AND next_review_date <= ?
                ORDER BY next_review_date ASC, created_at ASC
                LIMIT ?
                """,
                (user_id, module, now, limit),
            )
        elif question_type:
            cur = conn.execute(
                """
                SELECT * FROM mistakes
                WHERE user_id = ? AND question_type = ? AND next_review_date <= ?
                ORDER BY next_review_date ASC, created_at ASC
                LIMIT ?
                """,
                (user_id, question_type, now, limit),
            )
        else:
            cur = conn.execute(
                """
                SELECT * FROM mistakes
                WHERE user_id = ? AND next_review_date <= ?
                ORDER BY next_review_date ASC, created_at ASC
                LIMIT ?
                """,
                (user_id, now, limit),
            )
        rows = []
        for row in cur.fetchall():
            item = dict(row)
            item["tags"] = json.loads(item["tags"]) if item["tags"] else []
            rows.append(item)
        return rows
    finally:
        conn.close()


def get_due_mistake_user_counts(now_ts: Optional[int] = None, limit: int = 500) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        cur = conn.execute(
            """
            SELECT user_id, COUNT(*) AS due_count, MIN(next_review_date) AS earliest_due
            FROM mistakes
            WHERE next_review_date <= ?
            GROUP BY user_id
            ORDER BY due_count DESC
            LIMIT ?
            """,
            (now, limit),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_mistake_by_id(mistake_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM mistakes WHERE id = ?", (mistake_id,))
        row = cur.fetchone()
        if not row:
            return None
        mistake = dict(row)
        mistake['tags'] = json.loads(mistake['tags']) if mistake['tags'] else []
        return mistake
    finally:
        conn.close()


def review_mistake(mistake_id: str, mastery_delta: float = 0.2) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT id, user_id, module, question_type, error_type, mastery_level
            FROM mistakes
            WHERE id = ?
            """,
            (mistake_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        current_mastery = float(row['mastery_level'] or 0.0)
        new_mastery = max(0.0, min(1.0, current_mastery + mastery_delta))
        now = int(time.time())
        # mastery越高，下次复习间隔越长
        interval_days = 1 if new_mastery < 0.4 else (3 if new_mastery < 0.7 else 7)
        next_review_date = now + interval_days * 24 * 3600
        conn.execute(
            "UPDATE mistakes SET last_reviewed_at = ?, next_review_date = ?, mastery_level = ? WHERE id = ?",
            (now, next_review_date, new_mastery, mistake_id)
        )
        conn.execute(
            """
            INSERT INTO mistake_reviews (
              id, mistake_id, user_id, module, question_type, error_type, reviewed_at,
              mastery_before, mastery_after, mastery_delta, next_review_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                mistake_id,
                str(row["user_id"] or ""),
                str(row["module"] or ""),
                str(row["question_type"] or ""),
                str(row["error_type"] or ""),
                now,
                round(current_mastery, 4),
                round(new_mastery, 4),
                round(new_mastery - current_mastery, 4),
                next_review_date,
                now,
            ),
        )
        conn.commit()
        return {
            "last_reviewed_at": now,
            "next_review_date": next_review_date,
            "mastery_level": new_mastery,
        }
    finally:
        conn.close()


def get_mistake_stats(user_id: str) -> Dict[str, Any]:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT module, COUNT(*) as cnt FROM mistakes WHERE user_id = ? GROUP BY module",
            (user_id,)
        )
        by_module = {row['module'] or "unknown": row['cnt'] for row in cur.fetchall()}
        cur2 = conn.execute("SELECT COUNT(*) as total FROM mistakes WHERE user_id = ?", (user_id,))
        total = cur2.fetchone()['total']
        return {"total": total, "by_module": by_module}
    finally:
        conn.close()


def get_mistake_analysis(user_id: str) -> Dict[str, Any]:
    conn = get_conn()
    try:
        now = int(time.time())
        total = conn.execute(
            "SELECT COUNT(*) AS total FROM mistakes WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"]
        due = conn.execute(
            "SELECT COUNT(*) AS cnt FROM mistakes WHERE user_id = ? AND next_review_date <= ?",
            (user_id, now),
        ).fetchone()["cnt"]
        avg_mastery = conn.execute(
            "SELECT AVG(mastery_level) AS avg_mastery FROM mistakes WHERE user_id = ?",
            (user_id,),
        ).fetchone()["avg_mastery"] or 0.0
        by_error_type = {
            row["error_type"] or "general": row["cnt"]
            for row in conn.execute(
                "SELECT error_type, COUNT(*) AS cnt FROM mistakes WHERE user_id = ? GROUP BY error_type",
                (user_id,),
            ).fetchall()
        }
        by_difficulty = {
            row["difficulty"] or "unknown": row["cnt"]
            for row in conn.execute(
                "SELECT difficulty, COUNT(*) AS cnt FROM mistakes WHERE user_id = ? GROUP BY difficulty",
                (user_id,),
            ).fetchall()
        }
        by_question_type = {
            row["question_type"] or "general": row["cnt"]
            for row in conn.execute(
                "SELECT question_type, COUNT(*) AS cnt FROM mistakes WHERE user_id = ? GROUP BY question_type",
                (user_id,),
            ).fetchall()
        }
        by_error_and_question_type = {
            f"{(row['error_type'] or 'general')}|{(row['question_type'] or 'general')}": row["cnt"]
            for row in conn.execute(
                """
                SELECT error_type, question_type, COUNT(*) AS cnt
                FROM mistakes
                WHERE user_id = ?
                GROUP BY error_type, question_type
                """,
                (user_id,),
            ).fetchall()
        }
        vocab_test_wrong_count = int(by_error_and_question_type.get("vocabulary_test_wrong|vocabulary_test", 0))
        vocab_test_wrong_ratio = round((vocab_test_wrong_count / total), 4) if total > 0 else 0.0
        return {
            "total": total,
            "due_count": due,
            "avg_mastery": round(float(avg_mastery), 4),
            "by_error_type": by_error_type,
            "by_difficulty": by_difficulty,
            "by_question_type": by_question_type,
            "by_error_and_question_type": by_error_and_question_type,
            "vocabulary_test_wrong_count": vocab_test_wrong_count,
            "vocabulary_test_wrong_ratio": vocab_test_wrong_ratio,
        }
    finally:
        conn.close()


def get_prioritized_mistake_review_queue(
    user_id: str,
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    next_review_from: Optional[int] = None,
    next_review_to: Optional[int] = None,
    limit: int = 30,
    now_ts: Optional[int] = None,
) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        conditions = ["user_id = ?"]
        params: list[Any] = [user_id]
        if module:
            conditions.append("module = ?")
            params.append(module)
        if question_type:
            conditions.append("question_type = ?")
            params.append(question_type)
        if next_review_from is not None:
            conditions.append("next_review_date >= ?")
            params.append(int(next_review_from))
        if next_review_to is not None:
            conditions.append("next_review_date <= ?")
            params.append(int(next_review_to))
        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT
              m.*,
              COALESCE(agg.bucket_count, 1) AS bucket_count,
              CAST(MAX(0, ? - COALESCE(m.next_review_date, 0)) AS REAL) / 86400.0 AS overdue_days
            FROM mistakes m
            LEFT JOIN (
              SELECT module, question_type, error_type, COUNT(*) AS bucket_count
              FROM mistakes
              WHERE user_id = ?
              GROUP BY module, question_type, error_type
            ) agg
              ON agg.module = m.module
             AND agg.question_type = m.question_type
             AND agg.error_type = m.error_type
            WHERE {where_clause}
            ORDER BY m.created_at DESC
        """
        rows = conn.execute(sql, (now, user_id, *params)).fetchall()

        items: list[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["tags"] = json.loads(item["tags"]) if item.get("tags") else []
            mastery = float(item.get("mastery_level") or 0.0)
            overdue_days = max(0.0, float(item.get("overdue_days") or 0.0))
            created_days = max(0.0, (now - int(item.get("created_at") or now)) / 86400.0)
            due_boost = min(1.5, overdue_days / 3.0)
            bucket_count = int(item.get("bucket_count") or 1)
            bucket_boost = min(1.2, bucket_count / 5.0)
            weakness = 1.0 - mastery
            recency_boost = min(0.6, created_days / 5.0)
            priority_score = round(
                weakness * 0.50
                + due_boost * 0.28
                + bucket_boost * 0.14
                + recency_boost * 0.08,
                4,
            )
            base_gain = 0.12 + weakness * 0.18
            due_gain = min(0.08, overdue_days * 0.02)
            cluster_gain = min(0.05, bucket_count / 20.0)
            expected_gain = max(0.01, min(1.0 - mastery, base_gain + due_gain + cluster_gain))
            projected_mastery = max(0.0, min(1.0, mastery + expected_gain))
            if overdue_days >= 1:
                reason = f"已逾期 {overdue_days:.1f} 天"
            elif mastery < 0.4:
                reason = "掌握度偏低"
            elif bucket_count >= 3:
                reason = "同类错因聚集"
            else:
                reason = "近期新增需巩固"
            item["priority_score"] = priority_score
            item["priority_reason"] = reason
            item["expected_mastery_gain"] = round(expected_gain, 4)
            item["projected_mastery_after_review"] = round(projected_mastery, 4)
            items.append(item)
        items.sort(key=lambda x: float(x.get("priority_score") or 0.0), reverse=True)
        return items[: max(1, min(int(limit or 30), 300))]
    finally:
        conn.close()


def get_mistake_clusters(
    user_id: str,
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    limit: int = 20,
    now_ts: Optional[int] = None,
) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        conditions = ["user_id = ?"]
        params: list[Any] = [user_id]
        if module:
            conditions.append("module = ?")
            params.append(module)
        if question_type:
            conditions.append("question_type = ?")
            params.append(question_type)
        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT
              module,
              question_type,
              error_type,
              difficulty,
              COUNT(*) AS count,
              AVG(mastery_level) AS avg_mastery,
              SUM(CASE WHEN next_review_date <= ? THEN 1 ELSE 0 END) AS due_count,
              MAX(created_at) AS latest_created_at
            FROM mistakes
            WHERE {where_clause}
            GROUP BY module, question_type, error_type, difficulty
            ORDER BY count DESC, due_count DESC, avg_mastery ASC
            LIMIT ?
        """
        rows = conn.execute(sql, (now, *params, max(1, min(limit, 200)))).fetchall()
        clusters: list[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            avg_mastery = float(item.get("avg_mastery") or 0.0)
            count = int(item.get("count") or 0)
            due_count = int(item.get("due_count") or 0)
            risk = round((1 - avg_mastery) * 0.6 + min(1.0, due_count / max(count, 1)) * 0.4, 4)
            item["avg_mastery"] = round(avg_mastery, 4)
            item["risk_score"] = risk
            clusters.append(item)
        return clusters
    finally:
        conn.close()


def get_mistake_trends(
    user_id: str,
    days: int = 7,
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    now_ts: Optional[int] = None,
) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        days = max(1, min(int(days or 7), 60))
        start_ts = now - (days - 1) * 24 * 3600
        day_start = start_ts - (start_ts % 86400)

        conditions = ["user_id = ?"]
        params: list[Any] = [user_id]
        if module:
            conditions.append("module = ?")
            params.append(module)
        if question_type:
            conditions.append("question_type = ?")
            params.append(question_type)
        where_clause = " AND ".join(conditions)

        rows = conn.execute(
            f"""
            SELECT created_at, next_review_date
            FROM mistakes
            WHERE {where_clause}
            """,
            params,
        ).fetchall()
        review_conditions = ["user_id = ?"]
        review_params: list[Any] = [user_id]
        if module:
            review_conditions.append("module = ?")
            review_params.append(module)
        if question_type:
            review_conditions.append("question_type = ?")
            review_params.append(question_type)
        review_where_clause = " AND ".join(review_conditions)
        review_rows = conn.execute(
            f"""
            SELECT reviewed_at
            FROM mistake_reviews
            WHERE {review_where_clause}
            """,
            review_params,
        ).fetchall()

        buckets: list[Dict[str, Any]] = []
        for i in range(days):
            s = day_start + i * 86400
            e = s + 86400 - 1
            created_count = 0
            reviewed_count = 0
            due_snapshot = 0
            for row in rows:
                created_at = int(row["created_at"] or 0)
                next_review_date = int(row["next_review_date"] or 0)
                if s <= created_at <= e:
                    created_count += 1
                if next_review_date and next_review_date <= e:
                    due_snapshot += 1
            for review_row in review_rows:
                reviewed_at = int(review_row["reviewed_at"] or 0)
                if reviewed_at and s <= reviewed_at <= e:
                    reviewed_count += 1
            label = time.strftime("%m-%d", time.localtime(s))
            buckets.append(
                {
                    "date": label,
                    "day_start": s,
                    "created_count": created_count,
                    "reviewed_count": reviewed_count,
                    "due_snapshot": due_snapshot,
                }
            )
        return buckets
    finally:
        conn.close()


def get_mistake_review_effectiveness(
    user_id: str,
    days: int = 7,
    module: Optional[str] = None,
    question_type: Optional[str] = None,
    now_ts: Optional[int] = None,
) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        days = max(1, min(int(days or 7), 60))
        start_ts = now - (days - 1) * 24 * 3600
        day_start = start_ts - (start_ts % 86400)
        day_end = day_start + days * 86400 - 1

        conditions = ["user_id = ?", "reviewed_at >= ?", "reviewed_at <= ?"]
        params: list[Any] = [user_id, day_start, day_end]
        if module:
            conditions.append("module = ?")
            params.append(module)
        if question_type:
            conditions.append("question_type = ?")
            params.append(question_type)
        where_clause = " AND ".join(conditions)

        rows = conn.execute(
            f"""
            SELECT
              CAST(reviewed_at / 86400 AS INTEGER) * 86400 AS day_start,
              COUNT(*) AS review_count,
              AVG(mastery_before) AS avg_mastery_before,
              AVG(mastery_after) AS avg_mastery_after,
              AVG(mastery_delta) AS avg_mastery_gain
            FROM mistake_reviews
            WHERE {where_clause}
            GROUP BY CAST(reviewed_at / 86400 AS INTEGER)
            ORDER BY day_start ASC
            """,
            params,
        ).fetchall()

        daily_map: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            key = int(row["day_start"] or 0)
            daily_map[key] = {
                "review_count": int(row["review_count"] or 0),
                "avg_mastery_before": round(float(row["avg_mastery_before"] or 0.0), 4),
                "avg_mastery_after": round(float(row["avg_mastery_after"] or 0.0), 4),
                "avg_mastery_gain": round(float(row["avg_mastery_gain"] or 0.0), 4),
            }

        buckets: list[Dict[str, Any]] = []
        for i in range(days):
            s = day_start + i * 86400
            item = daily_map.get(
                s,
                {
                    "review_count": 0,
                    "avg_mastery_before": 0.0,
                    "avg_mastery_after": 0.0,
                    "avg_mastery_gain": 0.0,
                },
            )
            item["date"] = time.strftime("%m-%d", time.localtime(s))
            item["day_start"] = s
            buckets.append(item)
        return buckets
    finally:
        conn.close()


def get_mistake_hotspots(
    user_id: str,
    days: int = 14,
    module: Optional[str] = None,
    now_ts: Optional[int] = None,
    limit: int = 30,
) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        days = max(1, min(int(days or 14), 90))
        start_ts = now - days * 24 * 3600
        conditions = ["user_id = ?", "created_at >= ?"]
        params: list[Any] = [user_id, start_ts]
        if module:
            conditions.append("module = ?")
            params.append(module)
        where_clause = " AND ".join(conditions)
        rows = conn.execute(
            f"""
            SELECT
              module,
              error_type,
              COUNT(*) AS count,
              SUM(CASE WHEN next_review_date <= ? THEN 1 ELSE 0 END) AS due_count,
              AVG(mastery_level) AS avg_mastery
            FROM mistakes
            WHERE {where_clause}
            GROUP BY module, error_type
            ORDER BY count DESC, due_count DESC
            LIMIT ?
            """,
            (now, *params, max(1, min(int(limit or 30), 200))),
        ).fetchall()
        result: list[Dict[str, Any]] = []
        for row in rows:
            count = int(row["count"] or 0)
            due_count = int(row["due_count"] or 0)
            avg_mastery = float(row["avg_mastery"] or 0.0)
            due_ratio = (due_count / max(1, count))
            risk_score = round((1.0 - avg_mastery) * 0.55 + due_ratio * 0.45, 4)
            result.append(
                {
                    "module": str(row["module"] or "unknown"),
                    "error_type": str(row["error_type"] or "general"),
                    "count": count,
                    "due_count": due_count,
                    "avg_mastery": round(avg_mastery, 4),
                    "risk_score": risk_score,
                }
            )
        result.sort(key=lambda x: (float(x["risk_score"]), int(x["count"])), reverse=True)
        return result
    finally:
        conn.close()


def get_mistake_recommendations(
    user_id: str,
    days: int = 14,
    module: Optional[str] = None,
    now_ts: Optional[int] = None,
    limit: int = 5,
) -> list[Dict[str, Any]]:
    hotspots = get_mistake_hotspots(
        user_id=user_id,
        days=days,
        module=module,
        now_ts=now_ts,
        limit=max(10, limit * 4),
    )
    if not hotspots:
        return []
    sorted_rows = sorted(
        hotspots,
        key=lambda x: (float(x.get("risk_score") or 0.0), int(x.get("count") or 0)),
        reverse=True,
    )
    recs: list[Dict[str, Any]] = []
    for idx, row in enumerate(sorted_rows[: max(1, min(limit, 20))]):
        risk_score = float(row.get("risk_score") or 0.0)
        count = int(row.get("count") or 0)
        due_count = int(row.get("due_count") or 0)
        avg_mastery = float(row.get("avg_mastery") or 0.0)
        if risk_score >= 0.7:
            action = "立即进行专项重练，优先处理高风险错因"
        elif risk_score >= 0.5:
            action = "纳入本周主训练项，并增加复习频次"
        else:
            action = "保持常规复习，观察后续变化"
        recs.append(
            {
                "rank": idx + 1,
                "module": str(row.get("module") or "unknown"),
                "error_type": str(row.get("error_type") or "general"),
                "risk_score": round(risk_score, 4),
                "mistake_count": count,
                "due_count": due_count,
                "avg_mastery": round(avg_mastery, 4),
                "action": action,
            }
        )
    return recs


def get_mistake_module_comparison(
    user_id: str,
    days: int = 14,
    now_ts: Optional[int] = None,
) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        days = max(1, min(int(days or 14), 90))
        start_ts = now - days * 24 * 3600
        rows = conn.execute(
            """
            SELECT
              module,
              COUNT(*) AS count,
              SUM(CASE WHEN next_review_date <= ? THEN 1 ELSE 0 END) AS due_count,
              AVG(mastery_level) AS avg_mastery,
              COUNT(DISTINCT error_type) AS unique_error_types
            FROM mistakes
            WHERE user_id = ? AND created_at >= ?
            GROUP BY module
            ORDER BY count DESC
            """,
            (now, user_id, start_ts),
        ).fetchall()
        result: list[Dict[str, Any]] = []
        for row in rows:
            count = int(row["count"] or 0)
            due_count = int(row["due_count"] or 0)
            avg_mastery = float(row["avg_mastery"] or 0.0)
            unique_error_types = int(row["unique_error_types"] or 0)
            due_ratio = due_count / max(1, count)
            risk_index = round((1.0 - avg_mastery) * 0.5 + due_ratio * 0.35 + min(1.0, unique_error_types / 8.0) * 0.15, 4)
            result.append(
                {
                    "module": str(row["module"] or "unknown"),
                    "count": count,
                    "due_count": due_count,
                    "avg_mastery": round(avg_mastery, 4),
                    "unique_error_types": unique_error_types,
                    "risk_index": risk_index,
                }
            )
        result.sort(key=lambda x: (float(x["risk_index"]), int(x["count"])), reverse=True)
        return result
    finally:
        conn.close()


def get_mistake_weekly_focus_plan(
    user_id: str,
    days: int = 14,
    total_daily_minutes: int = 90,
    now_ts: Optional[int] = None,
) -> Dict[str, Any]:
    modules = get_mistake_module_comparison(user_id=user_id, days=days, now_ts=now_ts)
    if not modules:
        return {
            "focus_module": "",
            "total_daily_minutes": total_daily_minutes,
            "module_allocations": [],
            "daily_blocks": [],
            "summary": "暂无足够数据生成主攻计划。",
        }

    scored: list[Dict[str, Any]] = []
    for row in modules:
        count = float(row.get("count") or 0)
        due = float(row.get("due_count") or 0)
        risk = float(row.get("risk_index") or 0.0)
        due_ratio = due / max(1.0, count)
        volume_signal = min(1.0, count / 20.0)
        urgency = risk * 0.7 + due_ratio * 0.2 + volume_signal * 0.1
        scored.append({**row, "_urgency": urgency})

    scored.sort(key=lambda x: float(x.get("_urgency") or 0.0), reverse=True)
    total_urgency = sum(float(x.get("_urgency") or 0.0) for x in scored) or 1.0

    allocations: list[Dict[str, Any]] = []
    remaining_percent = 100
    for idx, row in enumerate(scored[:4]):
        if idx == len(scored[:4]) - 1:
            percent = max(5, remaining_percent)
        else:
            raw = int(round(float(row.get("_urgency") or 0.0) / total_urgency * 100))
            percent = max(10, min(70, raw))
            remaining_percent -= percent
        remaining_percent = max(0, remaining_percent)
        minutes = max(10, int(round(total_daily_minutes * percent / 100.0)))
        reason = (
            f"风险{float(row.get('risk_index') or 0):.3f}"
            f"，到期{int(row.get('due_count') or 0)}"
            f"，错因覆盖{int(row.get('unique_error_types') or 0)}"
        )
        allocations.append(
            {
                "module": str(row.get("module") or "unknown"),
                "percent": percent,
                "minutes": minutes,
                "reason": reason,
            }
        )

    allocations.sort(key=lambda x: int(x.get("percent") or 0), reverse=True)
    focus_module = str(allocations[0]["module"]) if allocations else ""
    daily_blocks = [
        {
            "block": idx + 1,
            "module": x["module"],
            "minutes": x["minutes"],
        }
        for idx, x in enumerate(allocations)
    ]
    summary = (
        f"建议本周优先主攻 {focus_module}，"
        f"每日学习总时长约 {total_daily_minutes} 分钟，按风险分配到各模块。"
    )
    return {
        "focus_module": focus_module,
        "total_daily_minutes": total_daily_minutes,
        "module_allocations": allocations,
        "daily_blocks": daily_blocks,
        "summary": summary,
    }


# Vocabulary DAO
def save_vocabulary(vocab_id: str, user_id: str, vocab_data: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        now = int(time.time())
        word = str(vocab_data.get("word", "") or "").strip()
        normalized_word = _normalize_vocab_word(word)
        existing_id = None
        if normalized_word:
            cur = conn.execute(
                """
                SELECT id
                FROM vocabulary
                WHERE user_id = ? AND lower(trim(word)) = ?
                LIMIT 1
                """,
                (user_id, normalized_word),
            )
            row = cur.fetchone()
            if row:
                existing_id = str(row["id"])

        target_id = existing_id or vocab_id
        if existing_id:
            conn.execute(
                """
                UPDATE vocabulary
                SET word = ?,
                    definition = ?,
                    examples = ?,
                    pronunciation = ?,
                    part_of_speech = ?,
                    tags = ?,
                    source_module = ?,
                    mastery_level = ?,
                    last_reviewed_at = ?,
                    next_review_date = ?
                WHERE id = ?
                """,
                (
                    word,
                    vocab_data.get("definition", ""),
                    json.dumps(vocab_data.get("examples", [])),
                    vocab_data.get("pronunciation", ""),
                    vocab_data.get("part_of_speech", ""),
                    json.dumps(vocab_data.get("tags", [])),
                    vocab_data.get("source_module", ""),
                    vocab_data.get("mastery_level", 0.0),
                    now,
                    now + 24 * 3600,
                    target_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO vocabulary (
                  id, user_id, word, definition, examples, pronunciation,
                  part_of_speech, tags, source_module, mastery_level,
                  last_reviewed_at, next_review_date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    user_id,
                    word,
                    vocab_data.get("definition", ""),
                    json.dumps(vocab_data.get("examples", [])),
                    vocab_data.get("pronunciation", ""),
                    vocab_data.get("part_of_speech", ""),
                    json.dumps(vocab_data.get("tags", [])),
                    vocab_data.get("source_module", ""),
                    vocab_data.get("mastery_level", 0.0),
                    now,
                    now + 24 * 3600,
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_user_vocabulary(user_id: str, limit: int = 100) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM vocabulary WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        vocab_list = []
        for row in cur.fetchall():
            vocab = dict(row)
            vocab['examples'] = json.loads(vocab['examples']) if vocab['examples'] else []
            vocab['tags'] = json.loads(vocab['tags']) if vocab['tags'] else []
            vocab_list.append(vocab)
        return vocab_list
    finally:
        conn.close()


def get_due_vocabulary(user_id: str, limit: int = 100, now_ts: Optional[int] = None) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        cur = conn.execute(
            """
            SELECT * FROM vocabulary
            WHERE user_id = ? AND next_review_date <= ?
            ORDER BY next_review_date ASC, created_at ASC
            LIMIT ?
            """,
            (user_id, now, limit),
        )
        rows = []
        for row in cur.fetchall():
            item = dict(row)
            item["examples"] = json.loads(item["examples"]) if item["examples"] else []
            item["tags"] = json.loads(item["tags"]) if item["tags"] else []
            rows.append(item)
        return rows
    finally:
        conn.close()


def get_due_vocabulary_user_counts(now_ts: Optional[int] = None, limit: int = 500) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        cur = conn.execute(
            """
            SELECT user_id, COUNT(*) AS due_count, MIN(next_review_date) AS earliest_due
            FROM vocabulary
            WHERE next_review_date <= ?
            GROUP BY user_id
            ORDER BY due_count DESC
            LIMIT ?
            """,
            (now, limit),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_vocabulary_by_id(vocab_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM vocabulary WHERE id = ?", (vocab_id,))
        row = cur.fetchone()
        if not row:
            return None
        item = dict(row)
        item["examples"] = json.loads(item["examples"]) if item["examples"] else []
        item["tags"] = json.loads(item["tags"]) if item["tags"] else []
        return item
    finally:
        conn.close()


def review_vocabulary(vocab_id: str, mastery_delta: float = 0.15) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT user_id, mastery_level FROM vocabulary WHERE id = ?", (vocab_id,))
        row = cur.fetchone()
        if not row:
            return None
        user_id = str(row["user_id"] or "")
        current_mastery = float(row["mastery_level"] or 0.0)
        new_mastery = max(0.0, min(1.0, current_mastery + mastery_delta))
        now = int(time.time())
        interval_days = 1 if new_mastery < 0.35 else (3 if new_mastery < 0.6 else (7 if new_mastery < 0.85 else 14))
        next_review_date = now + interval_days * 24 * 3600
        conn.execute(
            "UPDATE vocabulary SET last_reviewed_at = ?, next_review_date = ?, mastery_level = ? WHERE id = ?",
            (now, next_review_date, new_mastery, vocab_id),
        )
        conn.execute(
            """
            INSERT INTO vocabulary_reviews (
              id, vocab_id, user_id, reviewed_at,
              mastery_before, mastery_after, mastery_delta,
              next_review_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                vocab_id,
                user_id,
                now,
                round(current_mastery, 4),
                round(new_mastery, 4),
                round(new_mastery - current_mastery, 4),
                next_review_date,
                now,
            ),
        )
        conn.commit()
        return {
            "last_reviewed_at": now,
            "next_review_date": next_review_date,
            "mastery_level": new_mastery,
        }
    finally:
        conn.close()


def get_vocabulary_stats(user_id: str) -> Dict[str, Any]:
    conn = get_conn()
    try:
        now = int(time.time())
        total = conn.execute(
            "SELECT COUNT(*) AS total FROM vocabulary WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"]
        due = conn.execute(
            "SELECT COUNT(*) AS due FROM vocabulary WHERE user_id = ? AND next_review_date <= ?",
            (user_id, now),
        ).fetchone()["due"]
        avg_mastery = conn.execute(
            "SELECT AVG(mastery_level) AS avg_mastery FROM vocabulary WHERE user_id = ?",
            (user_id,),
        ).fetchone()["avg_mastery"] or 0.0
        by_source = {
            row["source_module"] or "unknown": row["cnt"]
            for row in conn.execute(
                "SELECT source_module, COUNT(*) AS cnt FROM vocabulary WHERE user_id = ? GROUP BY source_module",
                (user_id,),
            ).fetchall()
        }
        return {
            "total": total,
            "due_count": due,
            "avg_mastery": round(float(avg_mastery), 4),
            "by_source_module": by_source,
        }
    finally:
        conn.close()


def save_vocabulary_strategy_session(
    user_id: str,
    strategy: str,
    words: list[Dict[str, Any]],
    now_ts: Optional[int] = None,
) -> str:
    if not words:
        return ""
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        session_id = str(uuid4())
        safe_strategy = str(strategy or "spaced").strip().lower() or "spaced"
        word_count = len(words)
        due_count = 0
        scheduler_scores: list[float] = []
        masteries: list[float] = []
        for row in words:
            next_review = int(row.get("next_review_date") or 0)
            if next_review and next_review <= now:
                due_count += 1
            scheduler_scores.append(float(row.get("scheduler_score") or 0.0))
            masteries.append(float(row.get("mastery_level") or 0.0))
        avg_scheduler_score = round(sum(scheduler_scores) / max(1, len(scheduler_scores)), 6)
        avg_mastery = round(sum(masteries) / max(1, len(masteries)), 6)
        conn.execute(
            """
            INSERT INTO vocabulary_strategy_sessions (
              id, user_id, strategy, word_count, due_count,
              avg_scheduler_score, avg_mastery, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_id,
                safe_strategy,
                word_count,
                due_count,
                avg_scheduler_score,
                avg_mastery,
                now,
            ),
        )
        conn.executemany(
            """
            INSERT INTO vocabulary_strategy_session_words (
              id, session_id, user_id, strategy, word_id,
              mastery_at_session, scheduler_score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(uuid4()),
                    session_id,
                    user_id,
                    safe_strategy,
                    str(row.get("id") or ""),
                    round(float(row.get("mastery_level") or 0.0), 4),
                    round(float(row.get("scheduler_score") or 0.0), 6),
                    now,
                )
                for row in words
                if str(row.get("id") or "").strip()
            ],
        )
        conn.commit()
        return session_id
    finally:
        conn.close()


def get_vocabulary_strategy_insights(
    user_id: str,
    days: int = 14,
    now_ts: Optional[int] = None,
) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        now = int(now_ts or time.time())
        days = max(1, min(int(days or 14), 90))
        start_ts = now - days * 24 * 3600
        base_rows = conn.execute(
            """
            SELECT
              strategy,
              COUNT(*) AS session_count,
              SUM(word_count) AS total_words,
              SUM(due_count) AS total_due_words,
              AVG(avg_scheduler_score) AS avg_scheduler_score,
              AVG(avg_mastery) AS avg_mastery
            FROM vocabulary_strategy_sessions
            WHERE user_id = ? AND created_at >= ?
            GROUP BY strategy
            ORDER BY session_count DESC, strategy ASC
            """,
            (user_id, start_ts),
        ).fetchall()
        if not base_rows:
            return []

        strategy_word_rows = conn.execute(
            """
            SELECT strategy, word_id, created_at
            FROM vocabulary_strategy_session_words
            WHERE user_id = ? AND created_at >= ?
            """,
            (user_id, start_ts),
        ).fetchall()
        word_ids = sorted(
            {
                str(r["word_id"] or "").strip()
                for r in strategy_word_rows
                if str(r["word_id"] or "").strip()
            }
        )
        horizon_ts = now + 7 * 24 * 3600

        review_stats_by_word: Dict[str, Dict[str, float]] = {}
        if word_ids:
            placeholders = ",".join(["?"] * len(word_ids))
            review_rows = conn.execute(
                f"""
                SELECT vocab_id, COUNT(*) AS review_count, AVG(mastery_delta) AS avg_gain
                FROM vocabulary_reviews
                WHERE user_id = ? AND reviewed_at >= ? AND reviewed_at <= ? AND vocab_id IN ({placeholders})
                GROUP BY vocab_id
                """,
                (user_id, start_ts, horizon_ts, *word_ids),
            ).fetchall()
            for row in review_rows:
                vid = str(row["vocab_id"] or "").strip()
                if not vid:
                    continue
                review_stats_by_word[vid] = {
                    "review_count": float(row["review_count"] or 0),
                    "avg_gain": float(row["avg_gain"] or 0.0),
                }

        wrong_count_by_word: Dict[str, int] = {}
        mistake_rows = conn.execute(
            """
            SELECT tags
            FROM mistakes
            WHERE user_id = ? AND module = 'vocabulary' AND created_at >= ? AND created_at <= ?
            """,
            (user_id, start_ts, horizon_ts),
        ).fetchall()
        for row in mistake_rows:
            tags_raw = str(row["tags"] or "").strip()
            if not tags_raw:
                continue
            try:
                tags = json.loads(tags_raw)
            except Exception:
                tags = []
            if not isinstance(tags, list):
                continue
            for tag in tags:
                text = str(tag or "").strip()
                if text.startswith("word_id:"):
                    wid = text.split("word_id:", 1)[1].strip()
                    if wid:
                        wrong_count_by_word[wid] = wrong_count_by_word.get(wid, 0) + 1
                    break

        strategy_to_words: Dict[str, set[str]] = {}
        for row in strategy_word_rows:
            strategy_key = str(row["strategy"] or "spaced")
            wid = str(row["word_id"] or "").strip()
            if not wid:
                continue
            strategy_to_words.setdefault(strategy_key, set()).add(wid)

        result: list[Dict[str, Any]] = []
        for row in base_rows:
            strategy_key = str(row["strategy"] or "spaced")
            words_for_strategy = strategy_to_words.get(strategy_key, set())
            reviewed_words = 0
            total_review_count = 0.0
            gains: list[float] = []
            wrong_count = 0
            for wid in words_for_strategy:
                review_stat = review_stats_by_word.get(wid)
                if review_stat:
                    reviewed_words += 1
                    total_review_count += float(review_stat.get("review_count") or 0.0)
                    gains.append(float(review_stat.get("avg_gain") or 0.0))
                wrong_count += int(wrong_count_by_word.get(wid, 0))
            total_words = int(row["total_words"] or 0)
            wrong_rate = round((wrong_count / max(1, total_words)), 4)
            avg_gain = round((sum(gains) / max(1, len(gains))), 4) if gains else 0.0
            result.append(
                {
                    "strategy": strategy_key,
                    "session_count": int(row["session_count"] or 0),
                    "total_words": total_words,
                    "total_due_words": int(row["total_due_words"] or 0),
                    "avg_scheduler_score": round(float(row["avg_scheduler_score"] or 0.0), 4),
                    "avg_mastery": round(float(row["avg_mastery"] or 0.0), 4),
                    "reviewed_words_7d": int(reviewed_words),
                    "review_events_7d": int(round(total_review_count)),
                    "avg_mastery_gain_7d": avg_gain,
                    "wrong_count_7d": int(wrong_count),
                    "wrong_rate_7d": wrong_rate,
                }
            )
        return result
    finally:
        conn.close()
