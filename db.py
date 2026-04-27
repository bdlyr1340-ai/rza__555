from __future__ import annotations

import asyncpg
from typing import Any, Dict, List, Optional

import config

_pool: Optional[asyncpg.Pool] = None

MIGRATIONS = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    language TEXT NOT NULL DEFAULT 'ar',
    credits INTEGER NOT NULL DEFAULT 3,
    total_actions INTEGER NOT NULL DEFAULT 0,
    referred_by BIGINT,
    is_banned BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT NOT NULL,
    referred_id BIGINT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
"""


async def connect() -> None:
    global _pool
    if _pool is not None:
        return
    _pool = await asyncpg.create_pool(
        dsn=config.DATABASE_URL,
        min_size=1,
        max_size=5,
        command_timeout=30,
    )
    async with _pool.acquire() as conn:
        await conn.execute(MIGRATIONS)


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database is not connected")
    return _pool


async def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str], referred_by: Optional[int] = None) -> Dict[str, Any]:
    async with pool().acquire() as conn:
        old = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        if old:
            row = await conn.fetchrow(
                """
                UPDATE users
                   SET username=$2, first_name=$3, last_seen_at=NOW()
                 WHERE user_id=$1
             RETURNING *
                """,
                user_id, username, first_name,
            )
            return dict(row)

        row = await conn.fetchrow(
            """
            INSERT INTO users (user_id, username, first_name, credits, referred_by)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            user_id, username, first_name, config.DEFAULT_CREDITS, referred_by,
        )

        if referred_by and referred_by != user_id:
            inserted = await conn.fetchrow(
                """
                INSERT INTO referrals (referrer_id, referred_id)
                VALUES ($1, $2)
                ON CONFLICT (referred_id) DO NOTHING
                RETURNING id
                """,
                referred_by, user_id,
            )
            if inserted:
                await conn.execute(
                    "UPDATE users SET credits = credits + $1 WHERE user_id=$2",
                    config.REFERRAL_BONUS, referred_by,
                )
        return dict(row)


async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        return dict(row) if row else None


async def set_language(user_id: int, language: str) -> None:
    async with pool().acquire() as conn:
        await conn.execute("UPDATE users SET language=$1 WHERE user_id=$2", language, user_id)


async def add_credits(user_id: int, amount: int) -> Optional[int]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE users SET credits = credits + $1 WHERE user_id=$2 RETURNING credits",
            amount, user_id,
        )
        return int(row["credits"]) if row else None


async def set_banned(user_id: int, banned: bool) -> None:
    async with pool().acquire() as conn:
        await conn.execute("UPDATE users SET is_banned=$1 WHERE user_id=$2", banned, user_id)


async def stats() -> Dict[str, Any]:
    async with pool().acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        today = await conn.fetchval("SELECT COUNT(*) FROM users WHERE created_at::date = CURRENT_DATE")
        banned = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_banned=TRUE")
        refs = await conn.fetchval("SELECT COUNT(*) FROM referrals")
        return {
            "users": int(users or 0),
            "today": int(today or 0),
            "banned": int(banned or 0),
            "referrals": int(refs or 0),
        }


async def all_active_user_ids() -> List[int]:
    async with pool().acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users WHERE is_banned=FALSE")
        return [int(row["user_id"]) for row in rows]
