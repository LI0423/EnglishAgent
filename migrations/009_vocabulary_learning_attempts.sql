CREATE TABLE IF NOT EXISTS vocabulary_learning_attempts (
  id TEXT PRIMARY KEY,
  vocab_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  session_id TEXT,
  strategy TEXT,
  recall_text TEXT DEFAULT '',
  cloze_answer TEXT DEFAULT '',
  output_sentence TEXT DEFAULT '',
  self_rating TEXT DEFAULT '',
  recall_completed INTEGER NOT NULL DEFAULT 0,
  cloze_correct INTEGER NOT NULL DEFAULT 0,
  output_uses_word INTEGER NOT NULL DEFAULT 0,
  quality_score REAL NOT NULL DEFAULT 0.0,
  mastery_delta REAL NOT NULL DEFAULT 0.0,
  mastery_after REAL NOT NULL DEFAULT 0.0,
  next_review_date INTEGER,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vocab_learning_attempts_user_time
ON vocabulary_learning_attempts(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vocab_learning_attempts_vocab_time
ON vocabulary_learning_attempts(vocab_id, created_at DESC);
