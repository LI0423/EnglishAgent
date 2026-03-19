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
) -> list[Dict[str, Any]]:
    conn = get_conn()
    try:
        if module and question_type:
            cur = conn.execute(
                """
                SELECT * FROM mistakes
                WHERE user_id = ? AND module = ? AND question_type = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (user_id, module, question_type, limit),
            )
        elif module:
            cur = conn.execute(
                "SELECT * FROM mistakes WHERE user_id = ? AND module = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, module, limit)
            )
        elif question_type:
            cur = conn.execute(
                "SELECT * FROM mistakes WHERE user_id = ? AND question_type = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, question_type, limit),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM mistakes WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
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
        cur = conn.execute("SELECT mastery_level FROM mistakes WHERE id = ?", (mistake_id,))
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


# Vocabulary DAO
def save_vocabulary(vocab_id: str, user_id: str, vocab_data: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO vocabulary (
              id, user_id, word, definition, examples, pronunciation, 
              part_of_speech, tags, source_module, mastery_level, 
              last_reviewed_at, next_review_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vocab_id,
                user_id,
                vocab_data.get('word', ''),
                vocab_data.get('definition', ''),
                json.dumps(vocab_data.get('examples', [])),
                vocab_data.get('pronunciation', ''),
                vocab_data.get('part_of_speech', ''),
                json.dumps(vocab_data.get('tags', [])),
                vocab_data.get('source_module', ''),
                vocab_data.get('mastery_level', 0.0),
                int(time.time()),
                int(time.time()) + 24 * 3600,  # 1 day later
                int(time.time())
            )
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
        cur = conn.execute("SELECT mastery_level FROM vocabulary WHERE id = ?", (vocab_id,))
        row = cur.fetchone()
        if not row:
            return None
        current_mastery = float(row["mastery_level"] or 0.0)
        new_mastery = max(0.0, min(1.0, current_mastery + mastery_delta))
        now = int(time.time())
        interval_days = 1 if new_mastery < 0.35 else (3 if new_mastery < 0.6 else (7 if new_mastery < 0.85 else 14))
        next_review_date = now + interval_days * 24 * 3600
        conn.execute(
            "UPDATE vocabulary SET last_reviewed_at = ?, next_review_date = ?, mastery_level = ? WHERE id = ?",
            (now, next_review_date, new_mastery, vocab_id),
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
