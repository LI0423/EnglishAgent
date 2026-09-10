CREATE TABLE IF NOT EXISTS skill_tags (
  id TEXT PRIMARY KEY,
  skill_key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  parent_key TEXT DEFAULT '',
  metadata TEXT DEFAULT '{}',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_event_skill_tags (
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  skill_key TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 1.0,
  outcome REAL,
  created_at INTEGER NOT NULL,
  UNIQUE(event_id, skill_key)
);

CREATE INDEX IF NOT EXISTS idx_learning_event_skill_tags_event
ON learning_event_skill_tags(event_id);

CREATE INDEX IF NOT EXISTS idx_learning_event_skill_tags_skill
ON learning_event_skill_tags(skill_key);

CREATE TABLE IF NOT EXISTS user_skill_state (
  user_id TEXT NOT NULL,
  skill_key TEXT NOT NULL,
  category TEXT NOT NULL,
  mastery REAL NOT NULL DEFAULT 0.0,
  stability REAL NOT NULL DEFAULT 0.0,
  exposure_count INTEGER NOT NULL DEFAULT 0,
  correct_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  last_outcome REAL NOT NULL DEFAULT 0.0,
  last_practiced_at INTEGER NOT NULL DEFAULT 0,
  next_review_at INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY(user_id, skill_key)
);

CREATE INDEX IF NOT EXISTS idx_user_skill_state_user_category
ON user_skill_state(user_id, category, mastery);

CREATE INDEX IF NOT EXISTS idx_user_skill_state_review
ON user_skill_state(user_id, next_review_at);
