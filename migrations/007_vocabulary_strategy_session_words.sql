CREATE TABLE IF NOT EXISTS vocabulary_strategy_session_words (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  strategy TEXT NOT NULL,
  word_id TEXT NOT NULL,
  mastery_at_session REAL NOT NULL DEFAULT 0.0,
  scheduler_score REAL NOT NULL DEFAULT 0.0,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vocab_strategy_words_session
ON vocabulary_strategy_session_words(session_id, word_id);

CREATE INDEX IF NOT EXISTS idx_vocab_strategy_words_user_time
ON vocabulary_strategy_session_words(user_id, created_at DESC);
