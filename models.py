"""دوال التعامل مع الجداول."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from bot import config
from bot.db.connection import get_pool


# ============ USERS ============

async def upsert_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    referred_by: Optional[int] = None,
) -> Dict[str, Any]:
    """يُنشئ المستخدم لو غير موجود ويُحدّث بياناته. يُعيد صف المستخدم."""
    pool = get_pool()
    async with pool.acquire() as c:
        existing = await c.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if existing:
            row = await c.fetchrow(
                """
                UPDATE users
                   SET username = $2, first_name = $3, last_seen_at = NOW()
                 WHERE user_id = $1
             RETURNING *
                """,
                user_id, username, first_name,
            )
            return dict(row)

        # مستخدم جديد
        row = await c.fetchrow(
            """
            INSERT INTO users (user_id, username, first_name, credits, referred_by)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            user_id, username, first_name, config.DEFAULT_CREDITS, referred_by,
        )

        # سجّل الإحالة وأعطِ الكاسب البونص
        if referred_by and referred_by != user_id:
            try:
                await c.execute(
                    "INSERT INTO referrals (referrer_id, referred_id) VALUES ($1, $2)"
                    " ON CONFLICT (referred_id) DO NOTHING",
                    referred_by, user_id,
                )
                await c.execute(
                    "UPDATE users SET credits = credits + $1 WHERE user_id = $2",
                    config.REFERRAL_BONUS, referred_by,
                )
            except Exception:
                pass
        return dict(row)


async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return dict(row) if row else None


async def add_credits(user_id: int, amount: int) -> int:
    pool = get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "UPDATE users SET credits = credits + $1 WHERE user_id = $2 RETURNING credits",
            amount, user_id,
        )
        return int(row["credits"]) if row else 0


async def deduct_credit(user_id: int) -> bool:
    """يخصم نقطة لو فيه رصيد. يُعيد True عند النجاح."""
    pool = get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "UPDATE users SET credits = credits - 1 WHERE user_id = $1 AND credits > 0"
            " RETURNING credits",
            user_id,
        )
        return row is not None


async def set_banned(user_id: int, banned: bool) -> None:
    pool = get_pool()
    async with pool.acquire() as c:
        await c.execute("UPDATE users SET is_banned = $1 WHERE user_id = $2", banned, user_id)


async def is_banned(user_id: int) -> bool:
    u = await get_user(user_id)
    return bool(u and u.get("is_banned"))


async def all_user_ids() -> List[int]:
    pool = get_pool()
    async with pool.acquire() as c:
        rows = await c.fetch("SELECT user_id FROM users WHERE is_banned = FALSE")
        return [int(r["user_id"]) for r in rows]


# ============ VERIFICATIONS ============

async def log_verification_start(user_id: int, service: str, url: str) -> int:
    pool = get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "INSERT INTO verifications (user_id, service, sheerid_url, status)"
            " VALUES ($1, $2, $3, 'pending') RETURNING id",
            user_id, service, url,
        )
        await c.execute(
            "UPDATE users SET total_verifications = total_verifications + 1 WHERE user_id = $1",
            user_id,
        )
        return int(row["id"])


async def log_verification_finish(
    verification_id: int, user_id: int, success: bool, error: Optional[str] = None
) -> None:
    pool = get_pool()
    status = "success" if success else "failed"
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE verifications SET status = $1, error_message = $2 WHERE id = $3",
            status, error, verification_id,
        )
        if success:
            await c.execute(
                "UPDATE users SET successful_verifications = successful_verifications + 1"
                " WHERE user_id = $1",
                user_id,
            )


# ============ STATS (للأدمن) ============

async def admin_stats() -> Dict[str, Any]:
    pool = get_pool()
    async with pool.acquire() as c:
        users_total       = await c.fetchval("SELECT COUNT(*) FROM users")
        users_today       = await c.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at::date = CURRENT_DATE"
        )
        ver_total         = await c.fetchval("SELECT COUNT(*) FROM verifications")
        ver_today         = await c.fetchval(
            "SELECT COUNT(*) FROM verifications WHERE created_at::date = CURRENT_DATE"
        )
        ver_success       = await c.fetchval(
            "SELECT COUNT(*) FROM verifications WHERE status = 'success'"
        )
        per_service       = await c.fetch(
            "SELECT service, COUNT(*) AS n,"
            " COUNT(*) FILTER (WHERE status = 'success') AS ok"
            " FROM verifications GROUP BY service ORDER BY n DESC"
        )
    return {
        "users_total":   users_total or 0,
        "users_today":   users_today or 0,
        "ver_total":     ver_total or 0,
        "ver_today":     ver_today or 0,
        "ver_success":   ver_success or 0,
        "per_service":   [dict(r) for r in per_service],
    }
