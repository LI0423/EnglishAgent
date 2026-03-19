import json
import os
import re
import sqlite3
import threading
import time
from hashlib import sha1
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{1,}|[A-Za-z]{2,}", (text or "").lower())
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "what",
        "how",
        "why",
        "which",
        "请",
        "什么",
        "怎么",
        "如何",
        "为什么",
    }
    return [t for t in tokens if t not in stop]


def _overlap_score(query: str, text: str) -> float:
    q = set(_tokenize(query))
    t = set(_tokenize(text))
    if not q or not t:
        return 0.0
    return len(q & t) / max(1, len(q))


class HybridMemory:
    """
    短期记忆：进程内按 session_id 保存最近 N 轮。
    长期记忆：按 user_id 持久化到 JSONL，基于词重叠召回。
    """

    def __init__(self):
        self._short: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=12))
        self._lock = threading.Lock()
        self._db_inited_paths = set()

    def _ensure_sqlite_table(self, db_path: str) -> None:
        if not db_path:
            return
        if db_path in self._db_inited_paths:
            return
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agentic_long_memory (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT NOT NULL,
                  session_id TEXT,
                  module TEXT,
                  question TEXT,
                  answer_summary TEXT,
                  memory_key TEXT,
                  created_at INTEGER,
                  updated_at INTEGER,
                  expires_at INTEGER,
                  hit_count INTEGER DEFAULT 1,
                  extra TEXT
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alm_user_module_time "
                "ON agentic_long_memory(user_id, module, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alm_user_module_key "
                "ON agentic_long_memory(user_id, module, memory_key)"
            )
            conn.commit()
        finally:
            conn.close()
        self._db_inited_paths.add(db_path)

    @staticmethod
    def _memory_key(question: str) -> str:
        normalized = re.sub(r"\s+", " ", (question or "").strip().lower())
        return sha1(normalized.encode("utf-8")).hexdigest()

    def get_short_memory(self, session_id: str, window: int = 6) -> List[Dict[str, Any]]:
        if not session_id:
            return []
        turns = list(self._short.get(session_id, []))
        return turns[-max(1, window):]

    def add_short_memory(self, session_id: str, item: Dict[str, Any], maxlen: int = 12) -> None:
        if not session_id:
            return
        if session_id not in self._short or self._short[session_id].maxlen != maxlen:
            self._short[session_id] = deque(self._short.get(session_id, []), maxlen=maxlen)
        self._short[session_id].append(item)

    def retrieve_long_memory(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        module: str = "general",
        backend: str = "sqlite",
        ttl_seconds: int = 30 * 24 * 3600,
        db_path: Optional[str] = None,
        memory_file: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not user_id:
            return []
        if ttl_seconds < 0:
            return []

        if backend == "sqlite":
            if not db_path:
                return []
            self._ensure_sqlite_table(db_path)
            now = int(time.time())
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                # 过期清理
                conn.execute(
                    "DELETE FROM agentic_long_memory WHERE expires_at > 0 AND expires_at < ?",
                    (now,),
                )
                conn.commit()
                rows = conn.execute(
                    """
                    SELECT user_id, session_id, module, question, answer_summary, updated_at, extra
                    FROM agentic_long_memory
                    WHERE user_id = ?
                      AND (module = ? OR module = 'general')
                      AND (? <= 0 OR updated_at >= ?)
                    ORDER BY updated_at DESC
                    LIMIT 200
                    """,
                    (str(user_id), module, ttl_seconds, now - ttl_seconds),
                ).fetchall()
            finally:
                conn.close()

            hits: List[Dict[str, Any]] = []
            for r in rows:
                obj = dict(r)
                if isinstance(obj.get("extra"), str):
                    try:
                        obj["extra"] = json.loads(obj["extra"])
                    except Exception:
                        obj["extra"] = {}
                memory_text = f"{obj.get('question', '')}\n{obj.get('answer_summary', '')}"
                score = _overlap_score(query, memory_text)
                if score <= 0:
                    continue
                obj["score"] = round(score, 4)
                hits.append(obj)
            hits.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
            return hits[:max(1, top_k)]

        # JSONL fallback
        if not memory_file or not os.path.exists(memory_file):
            return []
        hits = []
        now = int(time.time())
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    if str(obj.get("user_id")) != str(user_id):
                        continue
                    ts = int(obj.get("ts") or 0)
                    if ttl_seconds > 0 and ts < now - ttl_seconds:
                        continue
                    if obj.get("module") not in (module, "general", None):
                        continue
                    memory_text = f"{obj.get('question', '')}\n{obj.get('answer_summary', '')}"
                    score = _overlap_score(query, memory_text)
                    if score <= 0:
                        continue
                    obj["score"] = round(score, 4)
                    hits.append(obj)
        except Exception:
            return []
        hits.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
        return hits[:max(1, top_k)]

    def append_long_memory(
        self,
        user_id: str,
        session_id: str,
        module: str,
        question: str,
        answer: str,
        backend: str = "sqlite",
        db_path: Optional[str] = None,
        ttl_seconds: int = 30 * 24 * 3600,
        dedup_window_seconds: int = 3600,
        memory_file: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not user_id:
            return
        now = int(time.time())
        question_text = (question or "").strip()[:300]
        answer_text = (answer or "").strip()[:500]
        extra_json = json.dumps(extra or {}, ensure_ascii=False)

        if backend == "sqlite":
            if not db_path:
                return
            self._ensure_sqlite_table(db_path)
            memory_key = self._memory_key(question_text)
            expires_at = now + ttl_seconds if ttl_seconds > 0 else (now - 1 if ttl_seconds < 0 else 0)
            with self._lock:
                conn = sqlite3.connect(db_path)
                try:
                    # 过期清理
                    conn.execute(
                        "DELETE FROM agentic_long_memory WHERE expires_at > 0 AND expires_at < ?",
                        (now,),
                    )
                    # 去重窗口内更新
                    row = conn.execute(
                        """
                        SELECT id, hit_count FROM agentic_long_memory
                        WHERE user_id = ? AND module = ? AND memory_key = ? AND updated_at >= ?
                        ORDER BY updated_at DESC LIMIT 1
                        """,
                        (str(user_id), module, memory_key, now - max(0, dedup_window_seconds)),
                    ).fetchone()
                    if row:
                        conn.execute(
                            """
                            UPDATE agentic_long_memory
                            SET session_id = ?, answer_summary = ?, updated_at = ?, expires_at = ?, extra = ?, hit_count = ?
                            WHERE id = ?
                            """,
                            (
                                str(session_id or ""),
                                answer_text,
                                now,
                                expires_at,
                                extra_json,
                                int(row[1] or 1) + 1,
                                int(row[0]),
                            ),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO agentic_long_memory
                            (user_id, session_id, module, question, answer_summary, memory_key, created_at, updated_at, expires_at, extra)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(user_id),
                                str(session_id or ""),
                                module,
                                question_text,
                                answer_text,
                                memory_key,
                                now,
                                now,
                                expires_at,
                                extra_json,
                            ),
                        )
                    conn.commit()
                finally:
                    conn.close()
            return

        # JSONL fallback
        if not memory_file:
            return
        parent = os.path.dirname(memory_file)
        if parent:
            os.makedirs(parent, exist_ok=True)
        payload = {
            "ts": now,
            "user_id": str(user_id),
            "session_id": str(session_id or ""),
            "module": module,
            "question": question_text,
            "answer_summary": answer_text,
            "extra": extra or {},
        }
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            with open(memory_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    @staticmethod
    def build_memory_hints(short_items: List[Dict[str, Any]], long_items: List[Dict[str, Any]]) -> List[str]:
        hints: List[str] = []
        for item in short_items[-3:]:
            q = (item.get("question") or "").strip()
            a = (item.get("answer") or "").strip()
            if q or a:
                hints.append(f"短期记忆: Q={q[:60]} A={a[:80]}")
        for item in long_items[:3]:
            q = (item.get("question") or "").strip()
            a = (item.get("answer_summary") or "").strip()
            hints.append(f"长期记忆: Q={q[:60]} A={a[:80]}")
        return hints
