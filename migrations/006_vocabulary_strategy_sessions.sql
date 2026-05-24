CREATE TABLE IF NOT EXISTS vocabulary_strategy_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  strategy TEXT NOT NULL,
  word_count INTEGER NOT NULL DEFAULT 0,
  due_count INTEGER NOT NULL DEFAULT 0,
  avg_scheduler_score REAL NOT NULL DEFAULT 0.0,
  avg_mastery REAL NOT NULL DEFAULT 0.0,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vocab_strategy_sessions_user_time
ON vocabulary_strategy_sessions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vocab_strategy_sessions_user_strategy
ON vocabulary_strategy_sessions(user_id, strategy, created_at DESC);
