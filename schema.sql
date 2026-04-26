CREATE TABLE IF NOT EXISTS users (
  telegram_id BIGINT PRIMARY KEY,
  username TEXT,
  full_name TEXT,
  language TEXT DEFAULT 'ar',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS requests (
  id BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT REFERENCES users(telegram_id),
  service TEXT NOT NULL,
  github_owner TEXT,
  github_repo TEXT,
  github_issue_number INTEGER,
  status TEXT DEFAULT 'new',
  note TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_requests_telegram_id ON requests(telegram_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
