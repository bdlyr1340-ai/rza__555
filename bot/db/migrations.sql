-- جداول البوت — تُنشأ وتُصلح تلقائياً عند أول تشغيل
-- هذا الملف يتحمل وجود جدول users قديم بدون عمود user_id

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS user_id BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits INTEGER NOT NULL DEFAULT 3;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_verifications INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS successful_verifications INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- لازم user_id يكون عليه Unique حتى جدول verifications يكدر يسوي Foreign Key عليه.
CREATE UNIQUE INDEX IF NOT EXISTS users_user_id_unique ON users(user_id);

CREATE TABLE IF NOT EXISTS verifications (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    service TEXT NOT NULL,
    sheerid_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verifications_user ON verifications(user_id);
CREATE INDEX IF NOT EXISTS idx_verifications_created ON verifications(created_at DESC);

CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT NOT NULL,
    referred_id BIGINT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);

-- بطاقات الدفع — يضيفها الأدمن ويستخدمها البوت تلقائياً
CREATE TABLE IF NOT EXISTS payment_cards (
    id SERIAL PRIMARY KEY,
    card_number TEXT NOT NULL,
    card_holder TEXT NOT NULL,
    expiry_month INTEGER NOT NULL,
    expiry_year INTEGER NOT NULL,
    cvv TEXT NOT NULL,
    added_by BIGINT,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    used_by BIGINT,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payment_cards_unused ON payment_cards(is_used) WHERE is_used = FALSE
