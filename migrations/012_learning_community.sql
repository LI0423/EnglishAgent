CREATE TABLE IF NOT EXISTS community_posts (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  post_type TEXT NOT NULL DEFAULT 'discussion',
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  tags TEXT DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'published',
  is_anonymous INTEGER NOT NULL DEFAULT 0,
  upvotes INTEGER NOT NULL DEFAULT 0,
  downvotes INTEGER NOT NULL DEFAULT 0,
  comment_count INTEGER NOT NULL DEFAULT 0,
  view_count INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_community_posts_created
ON community_posts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_community_posts_type_created
ON community_posts(post_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_community_posts_user_created
ON community_posts(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS community_comments (
  id TEXT PRIMARY KEY,
  post_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  content TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'published',
  is_anonymous INTEGER NOT NULL DEFAULT 0,
  upvotes INTEGER NOT NULL DEFAULT 0,
  downvotes INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_community_comments_post_created
ON community_comments(post_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_community_comments_user_created
ON community_comments(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS community_votes (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  vote INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_community_votes_user_target
ON community_votes(user_id, target_type, target_id);

CREATE INDEX IF NOT EXISTS idx_community_votes_target
ON community_votes(target_type, target_id);
