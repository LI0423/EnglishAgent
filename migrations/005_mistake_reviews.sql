CREATE TABLE IF NOT EXISTS mistake_reviews (
  id TEXT PRIMARY KEY,
  mistake_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  module TEXT,
  question_type TEXT,
  error_type TEXT,
  reviewed_at INTEGER NOT NULL,
  mastery_before REAL NOT NULL DEFAULT 0.0,
  mastery_after REAL NOT NULL DEFAULT 0.0,
  mastery_delta REAL NOT NULL DEFAULT 0.0,
  next_review_date INTEGER,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mistake_reviews_user_time
ON mistake_reviews(user_id, reviewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_mistake_reviews_mistake
ON mistake_reviews(mistake_id, reviewed_at DESC);
