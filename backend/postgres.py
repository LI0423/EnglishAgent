from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection
from psycopg2.extras import RealDictCursor


load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_POSTGRES_DSN = "postgresql://root:123456@127.0.0.1:5432/english_agent_vocab"
POSTGRES_DSN = os.environ.get("POSTGRES_DSN", DEFAULT_POSTGRES_DSN)


def get_pg_conn() -> connection:
    return psycopg2.connect(POSTGRES_DSN, cursor_factory=RealDictCursor)


@contextmanager
def pg_cursor(commit: bool = False) -> Iterator[RealDictCursor]:
    conn = get_pg_conn()
    try:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_ielts_vocabulary_bank() -> None:
    try:
        with pg_cursor(commit=True) as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ielts_vocabulary_bank (
                  id TEXT PRIMARY KEY,
                  book_id TEXT NOT NULL,
                  word_id TEXT NOT NULL,
                  word_rank INTEGER NOT NULL,
                  head_word TEXT NOT NULL,
                  definition_cn TEXT DEFAULT '',
                  definition_en TEXT DEFAULT '',
                  part_of_speech TEXT DEFAULT '',
                  examples JSONB DEFAULT '[]'::jsonb,
                  phrases JSONB DEFAULT '[]'::jsonb,
                  synonyms JSONB DEFAULT '[]'::jsonb,
                  related_words JSONB DEFAULT '[]'::jsonb,
                  uk_phone TEXT DEFAULT '',
                  us_phone TEXT DEFAULT '',
                  difficulty TEXT NOT NULL DEFAULT 'medium',
                  topics TEXT[] NOT NULL DEFAULT ARRAY['general']::TEXT[],
                  tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
                  raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                  UNIQUE (book_id, word_id)
                )
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_ielts_vocab_bank_book_head_word
                ON ielts_vocabulary_bank (book_id, lower(head_word))
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ielts_vocab_bank_filter
                ON ielts_vocabulary_bank (difficulty, word_rank)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ielts_vocab_bank_topics
                ON ielts_vocabulary_bank USING GIN (topics)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ielts_vocab_bank_head_word
                ON ielts_vocabulary_bank (lower(head_word))
                """
            )
    except Exception as exc:
        logger.warning("PostgreSQL IELTS vocabulary bank init skipped: %s", exc)
