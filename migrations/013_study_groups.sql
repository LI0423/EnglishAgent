CREATE TABLE IF NOT EXISTS study_groups (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  is_public INTEGER NOT NULL DEFAULT 1,
  max_members INTEGER NOT NULL DEFAULT 20,
  member_count INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_study_groups_owner
ON study_groups(owner_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_study_groups_public_created
ON study_groups(is_public, created_at DESC);

CREATE TABLE IF NOT EXISTS study_group_members (
  id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',
  joined_at INTEGER NOT NULL,
  last_checkin_at INTEGER NOT NULL DEFAULT 0,
  checkin_streak INTEGER NOT NULL DEFAULT 0,
  total_checkins INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_study_group_members_group_user
ON study_group_members(group_id, user_id);

CREATE INDEX IF NOT EXISTS idx_study_group_members_user
ON study_group_members(user_id, joined_at DESC);

CREATE TABLE IF NOT EXISTS study_group_checkins (
  id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  note TEXT DEFAULT '',
  score INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_study_group_checkins_group_created
ON study_group_checkins(group_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_study_group_checkins_user_created
ON study_group_checkins(user_id, created_at DESC);
