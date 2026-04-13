CREATE TABLE IF NOT EXISTS writing_submissions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  task_type TEXT NOT NULL,
  topic TEXT,
  content TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  review_count INTEGER NOT NULL DEFAULT 0,
  avg_overall_score REAL NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_writing_submissions_user_created
ON writing_submissions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_writing_submissions_status_created
ON writing_submissions(status, created_at ASC);

CREATE TABLE IF NOT EXISTS writing_peer_reviews (
  id TEXT PRIMARY KEY,
  submission_id TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  reviewee_id TEXT NOT NULL,
  tr_score REAL NOT NULL,
  cc_score REAL NOT NULL,
  lr_score REAL NOT NULL,
  gra_score REAL NOT NULL,
  overall_score REAL NOT NULL,
  strengths TEXT,
  improvements TEXT,
  comment_text TEXT,
  quality_tier TEXT NOT NULL DEFAULT 'basic',
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_writing_peer_reviews_submission_created
ON writing_peer_reviews(submission_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_writing_peer_reviews_reviewee_created
ON writing_peer_reviews(reviewee_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_writing_peer_reviews_unique_reviewer
ON writing_peer_reviews(submission_id, reviewer_id);
