CREATE TABLE IF NOT EXISTS gamification_events (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  source TEXT NOT NULL,
  source_id TEXT NOT NULL,
  points INTEGER NOT NULL,
  note TEXT DEFAULT '',
  metadata TEXT DEFAULT '{}',
  created_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_gamification_events_user_source
ON gamification_events(user_id, source, source_id);

CREATE INDEX IF NOT EXISTS idx_gamification_events_user_created
ON gamification_events(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS gamification_achievements (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  code TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  icon TEXT DEFAULT '🏅',
  unlocked_at INTEGER NOT NULL,
  metadata TEXT DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_gamification_achievements_user_code
ON gamification_achievements(user_id, code);

CREATE INDEX IF NOT EXISTS idx_gamification_achievements_user_unlocked
ON gamification_achievements(user_id, unlocked_at DESC);

CREATE TABLE IF NOT EXISTS gamification_redemptions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  item_code TEXT NOT NULL,
  item_name TEXT NOT NULL,
  cost_points INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'completed',
  created_at INTEGER NOT NULL,
  metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_gamification_redemptions_user_created
ON gamification_redemptions(user_id, created_at DESC);
