from __future__ import annotations

import json
import logging
import random
import time
from typing import Any, Dict, Iterable, List

from backend.db import get_user_vocabulary
from backend.postgres import init_ielts_vocabulary_bank, pg_cursor


logger = logging.getLogger(__name__)

TOPIC_KEYWORDS = {
    "education": {"education", "school", "student", "teacher", "learn", "study", "course", "university", "academic", "class"},
    "environment": {"environment", "climate", "pollution", "energy", "carbon", "wildlife", "nature", "recycle", "sustainable"},
    "technology": {"technology", "digital", "computer", "internet", "online", "data", "software", "device", "innovation"},
    "society": {"society", "social", "community", "culture", "family", "public", "policy", "population", "crime"},
    "work": {"work", "job", "career", "employee", "business", "company", "management", "income", "profession"},
    "health": {"health", "medical", "disease", "doctor", "hospital", "mental", "physical", "diet", "stress"},
}

LOW_VALUE_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "these", "those", "have", "has", "had",
    "was", "were", "are", "been", "being", "into", "onto", "over", "under", "about", "after",
    "before", "as", "of", "to", "in", "on", "at", "by",
}


def difficulty_from_rank(word_rank: int, total_count: int) -> str:
    if total_count <= 0:
        return "medium"
    ratio = word_rank / total_count
    if ratio <= 0.34:
        return "easy"
    if ratio <= 0.67:
        return "medium"
    return "hard"


def infer_topics(text: str) -> List[str]:
    lower = str(text or "").lower()
    topics = [topic for topic, keywords in TOPIC_KEYWORDS.items() if any(keyword in lower for keyword in keywords)]
    return topics or ["general"]


def normalize_word_record(raw_data: Dict[str, Any], total_count: int) -> Dict[str, Any]:
    word_rank = int(raw_data.get("wordRank") or 0)
    book_id = str(raw_data.get("bookId") or "IELTSluan_2")
    head_word = str(raw_data.get("headWord") or "").strip()
    word = (raw_data.get("content") or {}).get("word") or {}
    word_id = str(word.get("wordId") or f"{book_id}_{word_rank}")
    content = word.get("content") or {}

    trans = content.get("trans") or []
    definition_cn = "; ".join(str(item.get("tranCn") or "").strip() for item in trans if item.get("tranCn"))
    definition_en = "; ".join(str(item.get("tranOther") or "").strip() for item in trans if item.get("tranOther"))
    part_of_speech = str((trans[0] or {}).get("pos") or "") if trans else ""

    examples = [
        {"english": item.get("sContent", ""), "chinese": item.get("sCn", "")}
        for item in ((content.get("sentence") or {}).get("sentences") or [])
        if item.get("sContent") or item.get("sCn")
    ]
    phrases = [
        {"phrase": item.get("pContent", ""), "chinese": item.get("pCn", "")}
        for item in ((content.get("phrase") or {}).get("phrases") or [])
        if item.get("pContent") or item.get("pCn")
    ]
    synonyms = []
    for group in ((content.get("syno") or {}).get("synos") or []):
        synonyms.extend(str(item.get("w") or "").strip() for item in group.get("hwds", []) if item.get("w"))

    related_words = []
    for group in ((content.get("relWord") or {}).get("rels") or []):
        related_words.extend(str(item.get("hwd") or "").strip() for item in group.get("words", []) if item.get("hwd"))

    topic_text = " ".join(
        [
            head_word,
            definition_cn,
            definition_en,
            " ".join(x["english"] for x in examples),
            " ".join(x["phrase"] for x in phrases),
        ]
    )
    topics = infer_topics(topic_text)
    tags = sorted(set([book_id, part_of_speech, *topics] + (["has_examples"] if examples else []) + (["has_phrases"] if phrases else [])))

    return {
        "id": word_id,
        "book_id": book_id,
        "word_id": word_id,
        "word_rank": word_rank,
        "head_word": head_word,
        "definition_cn": definition_cn,
        "definition_en": definition_en,
        "part_of_speech": part_of_speech,
        "examples": examples,
        "phrases": phrases,
        "synonyms": [x for x in synonyms if x],
        "related_words": [x for x in related_words if x],
        "uk_phone": str(content.get("ukphone") or ""),
        "us_phone": str(content.get("usphone") or ""),
        "difficulty": difficulty_from_rank(word_rank, total_count),
        "topics": topics,
        "tags": [x for x in tags if x],
        "raw_json": raw_data,
    }


def upsert_word_records(records: Iterable[Dict[str, Any]]) -> int:
    init_ielts_vocabulary_bank()
    count = 0
    with pg_cursor(commit=True) as cur:
        for record in records:
            if not record.get("head_word"):
                continue
            cur.execute(
                """
                INSERT INTO ielts_vocabulary_bank (
                  id, book_id, word_id, word_rank, head_word,
                  definition_cn, definition_en, part_of_speech,
                  examples, phrases, synonyms, related_words,
                  uk_phone, us_phone, difficulty, topics, tags, raw_json, updated_at
                ) VALUES (
                  %(id)s, %(book_id)s, %(word_id)s, %(word_rank)s, %(head_word)s,
                  %(definition_cn)s, %(definition_en)s, %(part_of_speech)s,
                  %(examples)s::jsonb, %(phrases)s::jsonb, %(synonyms)s::jsonb, %(related_words)s::jsonb,
                  %(uk_phone)s, %(us_phone)s, %(difficulty)s, %(topics)s, %(tags)s, %(raw_json)s::jsonb, NOW()
                )
                ON CONFLICT (book_id, word_id) DO UPDATE SET
                  word_rank = EXCLUDED.word_rank,
                  head_word = EXCLUDED.head_word,
                  definition_cn = EXCLUDED.definition_cn,
                  definition_en = EXCLUDED.definition_en,
                  part_of_speech = EXCLUDED.part_of_speech,
                  examples = EXCLUDED.examples,
                  phrases = EXCLUDED.phrases,
                  synonyms = EXCLUDED.synonyms,
                  related_words = EXCLUDED.related_words,
                  uk_phone = EXCLUDED.uk_phone,
                  us_phone = EXCLUDED.us_phone,
                  difficulty = EXCLUDED.difficulty,
                  topics = EXCLUDED.topics,
                  tags = EXCLUDED.tags,
                  raw_json = EXCLUDED.raw_json,
                  updated_at = NOW()
                """,
                {
                    **record,
                    "examples": json.dumps(record.get("examples", []), ensure_ascii=False),
                    "phrases": json.dumps(record.get("phrases", []), ensure_ascii=False),
                    "synonyms": json.dumps(record.get("synonyms", []), ensure_ascii=False),
                    "related_words": json.dumps(record.get("related_words", []), ensure_ascii=False),
                    "raw_json": json.dumps(record.get("raw_json", {}), ensure_ascii=False),
                },
            )
            count += 1
    return count


def select_translation_core_words(
    difficulty: str = "medium",
    topic: str = "general",
    limit: int = 3,
    user_id: str = "",
) -> List[Dict[str, Any]]:
    personalized = _select_personal_vocabulary_words(user_id, topic=topic, limit=limit)
    if len(personalized) >= limit:
        return personalized[:limit]

    try:
        init_ielts_vocabulary_bank()
        safe_difficulty = difficulty if difficulty in {"easy", "medium", "hard"} else "medium"
        safe_topic = str(topic or "general").strip().lower() or "general"
        with pg_cursor() as cur:
            rows = _query_candidates(cur, safe_difficulty, safe_topic, limit * 8)
            if len(rows) < limit and safe_topic != "general":
                rows.extend(_query_candidates(cur, safe_difficulty, "general", limit * 8))
            if len(rows) < limit:
                rows.extend(_query_candidates(cur, "", safe_topic, limit * 8))
    except Exception as exc:
        logger.warning("PostgreSQL IELTS vocabulary selection skipped: %s", exc)
        return []

    seen = set()
    candidates = []
    for row in rows:
        word = str(row.get("head_word") or "").lower()
        if not word or word in seen or word in LOW_VALUE_WORDS:
            continue
        seen.add(word)
        candidates.append(dict(row))
    random.shuffle(candidates)
    merged = personalized[:]
    seen = {str(item.get("head_word") or "").strip().lower() for item in merged}
    for item in candidates:
        word = str(item.get("head_word") or "").strip().lower()
        if not word or word in seen:
            continue
        merged.append(item)
        seen.add(word)
        if len(merged) >= limit:
            break
    return merged[:limit]


def _select_personal_vocabulary_words(user_id: str, topic: str = "general", limit: int = 3) -> List[Dict[str, Any]]:
    if not user_id:
        return []
    try:
        words = get_user_vocabulary(str(user_id), 1000)
    except Exception as exc:
        logger.warning("Personal vocabulary selection skipped: %s", exc)
        return []

    safe_topic = str(topic or "general").strip().lower() or "general"
    now_ts = int(time.time())
    candidates: List[Dict[str, Any]] = []
    for row in words:
        word = str(row.get("word") or "").strip()
        if not word or word.lower() in LOW_VALUE_WORDS:
            continue
        tags = {str(tag or "").strip().lower() for tag in (row.get("tags") or []) if str(tag or "").strip()}
        if safe_topic != "general" and safe_topic not in tags:
            continue
        mastery = float(row.get("mastery_level") or 0.0)
        next_review = int(row.get("next_review_date") or 0)
        due_bonus = 1.0 if next_review and next_review <= now_ts else 0.0
        priority = due_bonus + max(0.0, 1.0 - mastery)
        candidates.append(
            {
                "word_id": str(row.get("id") or ""),
                "book_id": "personal_vocabulary",
                "word_rank": int(100000 - priority * 1000),
                "head_word": word,
                "definition_cn": str(row.get("definition") or ""),
                "definition_en": "",
                "part_of_speech": str(row.get("part_of_speech") or ""),
                # 个人词库的 examples 是纯字符串列表，这里归一化成 bank 同构，避免下游按 dict 取值报错
                "examples": [
                    x if isinstance(x, dict) else {"english": str(x or ""), "chinese": ""}
                    for x in (row.get("examples") or [])
                ],
                "phrases": [],
                "synonyms": [],
                "related_words": [],
                "uk_phone": str(row.get("pronunciation") or ""),
                "us_phone": "",
                "difficulty": "medium",
                "topics": sorted(tags) or ["general"],
                "tags": ["personal", *sorted(tags)],
                "_priority": priority,
            }
        )
    candidates.sort(key=lambda item: (-float(item.get("_priority") or 0.0), str(item.get("head_word") or "")))
    return candidates[:max(0, int(limit or 3))]


def list_ielts_vocabulary_bank(
    difficulty: str = "",
    topic: str = "",
    keyword: str = "",
    limit: int = 30,
) -> List[Dict[str, Any]]:
    try:
        init_ielts_vocabulary_bank()
        filters = ["length(head_word) > 1"]
        params: List[Any] = []
        safe_difficulty = str(difficulty or "").strip().lower()
        safe_topic = str(topic or "").strip().lower()
        safe_keyword = str(keyword or "").strip().lower()
        if safe_difficulty in {"easy", "medium", "hard"}:
            filters.append("difficulty = %s")
            params.append(safe_difficulty)
        if safe_topic and safe_topic != "general":
            filters.append("%s = ANY(topics)")
            params.append(safe_topic)
        if safe_keyword:
            filters.append("(lower(head_word) LIKE %s OR lower(definition_cn) LIKE %s OR lower(definition_en) LIKE %s)")
            like = f"%{safe_keyword}%"
            params.extend([like, like, like])
        sql = f"""
            SELECT word_id, book_id, word_rank, head_word, definition_cn, definition_en,
                   part_of_speech, examples, phrases, synonyms, related_words,
                   uk_phone, us_phone, difficulty, topics, tags
            FROM ielts_vocabulary_bank
            WHERE {" AND ".join(filters)}
            ORDER BY
              CASE difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
              word_rank ASC,
              head_word ASC
            LIMIT %s
        """
        params.append(max(1, min(int(limit or 30), 200)))
        with pg_cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        logger.warning("PostgreSQL IELTS vocabulary list skipped: %s", exc)
        return []


def get_ielts_vocabulary_bank_by_ids(word_ids: List[str]) -> List[Dict[str, Any]]:
    clean_ids = [str(x or "").strip() for x in word_ids if str(x or "").strip()]
    if not clean_ids:
        return []
    try:
        init_ielts_vocabulary_bank()
        with pg_cursor() as cur:
            cur.execute(
                """
                SELECT word_id, book_id, word_rank, head_word, definition_cn, definition_en,
                       part_of_speech, examples, phrases, synonyms, related_words,
                       uk_phone, us_phone, difficulty, topics, tags
                FROM ielts_vocabulary_bank
                WHERE word_id = ANY(%s)
                """,
                (clean_ids,),
            )
            rows = [dict(row) for row in cur.fetchall()]
        order = {word_id: idx for idx, word_id in enumerate(clean_ids)}
        rows.sort(key=lambda row: order.get(str(row.get("word_id")), 10_000))
        return rows
    except Exception as exc:
        logger.warning("PostgreSQL IELTS vocabulary lookup skipped: %s", exc)
        return []


def get_ielts_vocabulary_bank_by_head_word(word: str) -> Dict[str, Any] | None:
    """按词头精确查询。

    不能用 keyword LIKE 查询代替：它按 difficulty/word_rank 排序后截断，
    已存在的词（如 port/light/face）常常不在前若干条里，导致被误判为"未找到"。
    """
    clean = str(word or "").strip().lower()
    if not clean:
        return None
    try:
        init_ielts_vocabulary_bank()
        with pg_cursor() as cur:
            cur.execute(
                """
                SELECT word_id, book_id, word_rank, head_word, definition_cn, definition_en,
                       part_of_speech, examples, phrases, synonyms, related_words,
                       uk_phone, us_phone, difficulty, topics, tags
                FROM ielts_vocabulary_bank
                WHERE lower(head_word) = %s
                LIMIT 1
                """,
                (clean,),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.warning("PostgreSQL IELTS vocabulary exact lookup skipped: %s", exc)
        return None


def sample_word_definitions(
    exclude: str = "",
    limit: int = 3,
    part_of_speech: str = "",
    difficulty: str = "",
) -> List[str]:
    """随机采样若干释义，作为「再认」练习的干扰项。

    固定取词库前 N 条会让所有题目共用同一组干扰项（实测全部是 easy 段同一批词），
    使"不认识 → 再认"练习退化为"认位置"。
    传入 part_of_speech / difficulty 时优先在同词性、同难度带内采样，干扰项更难靠
    「词性不匹配」排除；为空则退回全库采样。
    """
    safe_limit = max(1, min(int(limit or 3), 10))
    safe_pos = str(part_of_speech or "").strip().lower()
    safe_difficulty = str(difficulty or "").strip().lower()
    try:
        init_ielts_vocabulary_bank()
        with pg_cursor() as cur:
            cur.execute(
                """
                SELECT definition_cn FROM (
                  SELECT DISTINCT definition_cn
                  FROM ielts_vocabulary_bank
                  WHERE definition_cn IS NOT NULL AND definition_cn <> ''
                    AND definition_cn <> %s
                    AND (%s = '' OR lower(part_of_speech) = %s)
                    AND (%s = '' OR lower(difficulty) = %s)
                ) AS candidates
                ORDER BY random()
                LIMIT %s
                """,
                (
                    str(exclude or ""),
                    safe_pos,
                    safe_pos,
                    safe_difficulty,
                    safe_difficulty,
                    safe_limit,
                ),
            )
            rows = cur.fetchall()
        return [
            str(row.get("definition_cn") or "").strip()
            for row in rows
            if str(row.get("definition_cn") or "").strip()
        ]
    except Exception as exc:
        logger.warning("PostgreSQL definition sampling skipped: %s", exc)
        return []


def get_ielts_vocabulary_bank_summary() -> Dict[str, Any]:
    try:
        init_ielts_vocabulary_bank()
        with pg_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM ielts_vocabulary_bank")
            total_row = cur.fetchone() or {}
            cur.execute(
                """
                SELECT difficulty, COUNT(*) AS count
                FROM ielts_vocabulary_bank
                GROUP BY difficulty
                ORDER BY difficulty
                """
            )
            difficulties = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT topic, COUNT(*) AS count
                FROM ielts_vocabulary_bank, unnest(topics) AS topic
                GROUP BY topic
                ORDER BY count DESC, topic ASC
                LIMIT 30
                """
            )
            topics = [dict(row) for row in cur.fetchall()]
        return {
            "total": int(total_row.get("total") or 0),
            "difficulties": difficulties,
            "topics": topics,
        }
    except Exception as exc:
        logger.warning("PostgreSQL IELTS vocabulary summary skipped: %s", exc)
        return {"total": 0, "difficulties": [], "topics": []}


def _query_candidates(cur, difficulty: str, topic: str, limit: int) -> List[Dict[str, Any]]:
    filters = ["length(head_word) > 2", "lower(head_word) <> ALL(%s)"]
    params: List[Any] = [list(LOW_VALUE_WORDS)]
    if difficulty:
        filters.append("difficulty = %s")
        params.append(difficulty)
    if topic and topic != "general":
        filters.append("%s = ANY(topics)")
        params.append(topic)
    sql = f"""
        SELECT word_id, book_id, word_rank, head_word, definition_cn, definition_en,
               part_of_speech, examples, phrases, difficulty, topics
        FROM ielts_vocabulary_bank
        WHERE {" AND ".join(filters)}
        ORDER BY random()
        LIMIT %s
    """
    params.append(limit)
    cur.execute(sql, params)
    return list(cur.fetchall())


def _example_text(item: Any) -> str:
    """兼容两种例句形态：bank 的 {english, chinese} 字典 与 个人词库的纯字符串。"""
    if isinstance(item, dict):
        english = str(item.get("english") or "").strip()
        chinese = str(item.get("chinese") or "").strip()
        return " / ".join(x for x in [english, chinese] if x)
    return str(item or "").strip()


def _phrase_text(item: Any) -> str:
    if isinstance(item, dict):
        phrase = str(item.get("phrase") or "").strip()
        chinese = str(item.get("chinese") or "").strip()
        return " / ".join(x for x in [phrase, chinese] if x)
    return str(item or "").strip()


def format_core_words_for_prompt(words: List[Dict[str, Any]]) -> str:
    parts = []
    for word in words:
        examples = word.get("examples") or []
        phrases = word.get("phrases") or []
        example_text = ""
        if isinstance(examples, list) and examples:
            text = _example_text(examples[0])
            if text:
                example_text = f"例句: {text}"
        phrase_text = ""
        if isinstance(phrases, list) and phrases:
            texts = [t for t in (_phrase_text(x) for x in phrases[:3]) if t]
            if texts:
                phrase_text = "搭配: " + "; ".join(texts)
        parts.append(
            f"- {word.get('head_word')} ({word.get('part_of_speech') or 'word'}): "
            f"{word.get('definition_cn') or word.get('definition_en') or ''} {phrase_text} {example_text}".strip()
        )
    return "\n".join(parts)
