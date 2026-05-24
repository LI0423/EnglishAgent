CREATE TABLE IF NOT EXISTS vocabulary_reviews (
  id TEXT PRIMARY KEY,
  vocab_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  reviewed_at INTEGER NOT NULL,
  mastery_before REAL NOT NULL DEFAULT 0.0,
  mastery_after REAL NOT NULL DEFAULT 0.0,
  mastery_delta REAL NOT NULL DEFAULT 0.0,
  next_review_date INTEGER,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vocabulary_reviews_user_time
ON vocabulary_reviews(user_id, reviewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_vocabulary_reviews_vocab_time
ON vocabulary_reviews(vocab_id, reviewed_at DESC);
