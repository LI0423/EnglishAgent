CREATE TABLE IF NOT EXISTS password_reset_codes (
  account_key TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  code TEXT NOT NULL,
  attempts INTEGER DEFAULT 0,
  expires_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_password_reset_codes_expires_at
ON password_reset_codes(expires_at);
