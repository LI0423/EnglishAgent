CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  email TEXT,
  phone TEXT UNIQUE,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  topic TEXT,
  type TEXT DEFAULT 'speaking',
  parts_json TEXT,
  transcript_text TEXT DEFAULT '',
  transcript_id TEXT,
  status TEXT DEFAULT 'in-progress',
  duration INTEGER DEFAULT 0,
  accuracy REAL DEFAULT 0.0,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS session_parts (
  session_id TEXT,
  idx INTEGER,
  type TEXT,
  prompt TEXT,
  PRIMARY KEY (session_id, idx)
);

CREATE TABLE IF NOT EXISTS transcripts (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  text TEXT,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS scores (
  session_id TEXT PRIMARY KEY,
  FC REAL,
  LR REAL,
  GR REAL,
  PR REAL,
  overall REAL,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS user_profiles (
  user_id TEXT PRIMARY KEY,
  target_band REAL,
  current_band_overall REAL,
  current_band_listening REAL,
  current_band_reading REAL,
  current_band_writing REAL,
  current_band_speaking REAL,
  skill_vocabulary REAL,
  skill_grammar REAL,
  skill_pronunciation REAL,
  skill_fluency REAL,
  skill_coherence REAL,
  learning_total_hours REAL,
  learning_sessions_count INTEGER,
  learning_streak_days INTEGER,
  learning_avg_daily_minutes REAL,
  weaknesses TEXT,
  strong_areas TEXT,
  created_at INTEGER,
  updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS diagnostic_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  start_time INTEGER,
  end_time INTEGER,
  modules TEXT,
  total_questions INTEGER,
  completed_questions INTEGER,
  estimated_band REAL,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS diagnostic_reports (
  id TEXT PRIMARY KEY,
  session_id TEXT,
  overall_band REAL,
  module_scores TEXT,
  weaknesses TEXT,
  recommendations TEXT,
  generated_at INTEGER
);

CREATE TABLE IF NOT EXISTS learning_plans (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  target_band REAL,
  start_date INTEGER,
  end_date INTEGER,
  daily_minutes INTEGER,
  focus_modules TEXT,
  status TEXT,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS daily_tasks (
  id TEXT PRIMARY KEY,
  plan_id TEXT,
  date INTEGER,
  tasks TEXT,
  completed INTEGER,
  created_at INTEGER,
  updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS mistakes (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  module TEXT,
  question_id TEXT,
  question_type TEXT,
  error_type TEXT,
  content TEXT,
  user_answer TEXT,
  correct_answer TEXT,
  explanation TEXT,
  difficulty TEXT,
  tags TEXT,
  created_at INTEGER,
  last_reviewed_at INTEGER,
  next_review_date INTEGER,
  mastery_level REAL
);

CREATE TABLE IF NOT EXISTS vocabulary (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  word TEXT,
  definition TEXT,
  examples TEXT,
  pronunciation TEXT,
  part_of_speech TEXT,
  tags TEXT,
  source_module TEXT,
  mastery_level REAL,
  last_reviewed_at INTEGER,
  next_review_date INTEGER,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS reminders (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  type TEXT,
  title TEXT,
  content TEXT,
  scheduled_at INTEGER,
  sent_at INTEGER,
  status TEXT DEFAULT 'pending',
  channel TEXT,
  metadata TEXT,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS reminder_preferences (
  user_id TEXT PRIMARY KEY,
  enabled INTEGER DEFAULT 1,
  channels TEXT,
  preferred_times TEXT,
  quiet_hours TEXT,
  created_at INTEGER,
  updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS learning_events (
  event_id TEXT PRIMARY KEY,
  user_id TEXT,
  event_type TEXT,
  event_name TEXT,
  properties TEXT,
  timestamp INTEGER,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS user_activities (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  activity_type TEXT,
  module TEXT,
  duration INTEGER,
  score REAL,
  metadata TEXT,
  created_at INTEGER,
  updated_at INTEGER
);
