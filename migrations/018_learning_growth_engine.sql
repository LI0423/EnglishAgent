CREATE TABLE IF NOT EXISTS learning_units (
  id TEXT PRIMARY KEY,
  unit_type TEXT NOT NULL,
  unit_key TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  source_modules TEXT DEFAULT '[]',
  ability_keys TEXT DEFAULT '[]',
  tags TEXT DEFAULT '[]',
  created_at INTEGER NOT NULL,
  updated_at INTEGER,
  UNIQUE(unit_type, unit_key)
);

CREATE TABLE IF NOT EXISTS user_unit_memory (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  unit_id TEXT NOT NULL,
  mastery_level REAL NOT NULL DEFAULT 0.0,
  memory_strength REAL NOT NULL DEFAULT 0.0,
  sm2_repetitions INTEGER NOT NULL DEFAULT 0,
  sm2_interval_days REAL NOT NULL DEFAULT 0.0,
  sm2_ease_factor REAL NOT NULL DEFAULT 2.5,
  sm2_lapses INTEGER NOT NULL DEFAULT 0,
  sm2_last_quality INTEGER,
  next_review_at INTEGER,
  last_seen_at INTEGER,
  updated_at INTEGER,
  UNIQUE(user_id, unit_id)
);

CREATE INDEX IF NOT EXISTS idx_user_unit_memory_due
ON user_unit_memory(user_id, next_review_at);

CREATE TABLE IF NOT EXISTS user_ability_growth (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  ability_key TEXT NOT NULL,
  current_score REAL NOT NULL DEFAULT 0.0,
  velocity REAL NOT NULL DEFAULT 0.0,
  stability REAL NOT NULL DEFAULT 0.0,
  confidence REAL NOT NULL DEFAULT 0.0,
  risk_level TEXT NOT NULL DEFAULT 'normal',
  sample_count INTEGER NOT NULL DEFAULT 0,
  last_active_at INTEGER,
  updated_at INTEGER,
  UNIQUE(user_id, ability_key)
);

CREATE INDEX IF NOT EXISTS idx_user_ability_growth_user_risk
ON user_ability_growth(user_id, risk_level, updated_at DESC);
