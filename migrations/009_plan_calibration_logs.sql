CREATE TABLE IF NOT EXISTS plan_calibration_logs (
  id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  before_daily_minutes INTEGER,
  after_daily_minutes INTEGER,
  before_focus_modules TEXT,
  after_focus_modules TEXT,
  source TEXT,
  note TEXT,
  created_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_plan_calibration_logs_plan_created
ON plan_calibration_logs(plan_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_plan_calibration_logs_user_created
ON plan_calibration_logs(user_id, created_at DESC);
