CREATE TABLE IF NOT EXISTS growth_campaigns (
  id TEXT PRIMARY KEY,
  created_by TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  campaign_type TEXT NOT NULL DEFAULT 'challenge',
  status TEXT NOT NULL DEFAULT 'draft',
  start_at INTEGER NOT NULL,
  end_at INTEGER NOT NULL,
  reward_points INTEGER NOT NULL DEFAULT 0,
  rules_json TEXT DEFAULT '{}',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_growth_campaigns_status_time
ON growth_campaigns(status, start_at, end_at);

CREATE INDEX IF NOT EXISTS idx_growth_campaigns_creator
ON growth_campaigns(created_by, created_at DESC);

CREATE TABLE IF NOT EXISTS growth_campaign_participants (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'joined',
  progress INTEGER NOT NULL DEFAULT 0,
  target INTEGER NOT NULL DEFAULT 1,
  joined_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  completed_at INTEGER
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_growth_campaign_participants_user
ON growth_campaign_participants(campaign_id, user_id);

CREATE INDEX IF NOT EXISTS idx_growth_campaign_participants_campaign
ON growth_campaign_participants(campaign_id, status, progress DESC);

CREATE TABLE IF NOT EXISTS growth_campaign_events (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  value INTEGER NOT NULL DEFAULT 1,
  metadata TEXT DEFAULT '{}',
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_growth_campaign_events_campaign_time
ON growth_campaign_events(campaign_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_growth_campaign_events_user_time
ON growth_campaign_events(user_id, created_at DESC);
