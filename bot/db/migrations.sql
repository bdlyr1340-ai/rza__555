-- Merged database schema — PostgreSQL (Railway)
-- Handles both fresh installs and upgrades from either bot

-- ════════════════════════════════════════════════
-- 1. Users
-- ════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS user_id        BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS username       TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name     TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits        INTEGER NOT NULL DEFAULT 3;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_verifications     INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS successful_verifications INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by    BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned      BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_checkin   TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE UNIQUE INDEX IF NOT EXISTS users_user_id_unique ON users(user_id);

-- ════════════════════════════════════════════════
-- 2. Verifications
-- ════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS verifications (
    id             SERIAL PRIMARY KEY,
    user_id        BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    service        TEXT NOT NULL,
    sheerid_url    TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'pending',
    result         TEXT,
    error_message  TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verifications_user    ON verifications(user_id);
CREATE INDEX IF NOT EXISTS idx_verifications_created ON verifications(created_at DESC);

-- ════════════════════════════════════════════════
-- 3. Referrals
-- ════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS referrals (
    id          SERIAL PRIMARY KEY,
    referrer_id BIGINT NOT NULL,
    referred_id BIGINT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);

-- ════════════════════════════════════════════════
-- 4. Payment Cards (from bot2)
-- ════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS payment_cards (
    id           SERIAL PRIMARY KEY,
    card_number  TEXT NOT NULL,
    card_holder  TEXT NOT NULL,
    expiry_month INTEGER NOT NULL,
    expiry_year  INTEGER NOT NULL,
    cvv          TEXT NOT NULL,
    added_by     BIGINT,
    is_used      BOOLEAN NOT NULL DEFAULT FALSE,
    used_by      BIGINT,
    used_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payment_cards_unused ON payment_cards(is_used) WHERE is_used = FALSE;

-- ════════════════════════════════════════════════
-- 5. Card Keys / Redeem Codes (from bot1)
-- ════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS card_keys (
    id           SERIAL PRIMARY KEY,
    key_code     TEXT UNIQUE NOT NULL,
    credits      INTEGER NOT NULL,
    max_uses     INTEGER NOT NULL DEFAULT 1,
    current_uses INTEGER NOT NULL DEFAULT 0,
    expire_at    TIMESTAMPTZ,
    created_by   BIGINT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_card_keys_code ON card_keys(key_code);

CREATE TABLE IF NOT EXISTS card_key_usage (
    id       SERIAL PRIMARY KEY,
    key_code TEXT NOT NULL,
    user_id  BIGINT NOT NULL,
    used_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_card_key_usage_key  ON card_key_usage(key_code);
CREATE INDEX IF NOT EXISTS idx_card_key_usage_user ON card_key_usage(user_id);

-- ════════════════════════════════════════════════
-- 6. Google Cookies (session reuse for Gemini auto)
-- ════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS google_cookies (
    gmail       TEXT PRIMARY KEY,
    cookies     JSONB NOT NULL,
    user_agent  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

