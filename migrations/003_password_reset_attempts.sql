CREATE TABLE IF NOT EXISTS password_reset_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_key TEXT NOT NULL,
  requested_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_password_reset_attempts_account_time
ON password_reset_attempts(account_key, requested_at);
