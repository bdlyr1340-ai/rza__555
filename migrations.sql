-- جداول البوت — تُنشأ تلقائياً عند أول تشغيل

CREATE TABLE IF NOT EXISTS users (
    user_id                 BIGINT       PRIMARY KEY,
    username                TEXT,
    first_name              TEXT,
    credits                 INTEGER      NOT NULL DEFAULT 3,
    total_verifications     INTEGER      NOT NULL DEFAULT 0,
    successful_verifications INTEGER     NOT NULL DEFAULT 0,
    referred_by             BIGINT,
    is_banned               BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_seen_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS verifications (
    id              SERIAL       PRIMARY KEY,
    user_id         BIGINT       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    service         TEXT         NOT NULL,
    sheerid_url     TEXT         NOT NULL,
    status          TEXT         NOT NULL DEFAULT 'pending',  -- pending | success | failed
    error_message   TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_verifications_user    ON verifications(user_id);
CREATE INDEX IF NOT EXISTS idx_verifications_created ON verifications(created_at DESC);

CREATE TABLE IF NOT EXISTS referrals (
    id           SERIAL       PRIMARY KEY,
    referrer_id  BIGINT       NOT NULL,
    referred_id  BIGINT       NOT NULL UNIQUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
