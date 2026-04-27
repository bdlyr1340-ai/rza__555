-- Safe bot tables. Prefix avoids conflict with old Railway tables.

CREATE TABLE IF NOT EXISTS rza_users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    credits INTEGER NOT NULL DEFAULT 3,
    total_verifications INTEGER NOT NULL DEFAULT 0,
    successful_verifications INTEGER NOT NULL DEFAULT 0,
    referred_by BIGINT,
    is_banned BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rza_verifications (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES rza_users(user_id) ON DELETE CASCADE,
    service TEXT NOT NULL,
    sheerid_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rza_verifications_user ON rza_verifications(user_id);
CREATE INDEX IF NOT EXISTS idx_rza_verifications_created ON rza_verifications(created_at DESC);

CREATE TABLE IF NOT EXISTS rza_referrals (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT NOT NULL,
    referred_id BIGINT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rza_referrals_referrer ON rza_referrals(referrer_id);
