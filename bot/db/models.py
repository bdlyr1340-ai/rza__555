"""Merged database models — async PostgreSQL via asyncpg."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from bot import config
from bot.db.connection import get_pool


# ════════════════════════════════════════════════
# Users
# ════════════════════════════════════════════════

async def upsert_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    referred_by: Optional[int] = None,
) -> Dict[str, Any]:
    pool = get_pool()
    async with pool.acquire() as c:
        existing = await c.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if existing:
            row = await c.fetchrow(
                """UPDATE users
                      SET username = $2, first_name = $3, last_seen_at = NOW()
                    WHERE user_id = $1
                RETURNING *""",
                user_id, username, first_name,
            )
            return dict(row)

        row = await c.fetchrow(
            """INSERT INTO users (user_id, username, first_name, credits, referred_by)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING *""",
            user_id, username, first_name, config.DEFAULT_CREDITS, referred_by,
        )

        if referred_by and referred_by != user_id:
            try:
                await c.execute(
                    "INSERT INTO referrals (referrer_id, referred_id) VALUES ($1, $2) "
                    "ON CONFLICT (referred_id) DO NOTHING",
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


async def deduct_credit(user_id: int, amount: int = 1) -> bool:
    pool = get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "UPDATE users SET credits = credits - $1 WHERE user_id = $2 AND credits >= $1 RETURNING credits",
            amount, user_id,
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


async def get_blacklist() -> List[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as c:
        rows = await c.fetch("SELECT * FROM users WHERE is_banned = TRUE")
        return [dict(r) for r in rows]


# ════════════════════════════════════════════════
# Daily check-in
# ════════════════════════════════════════════════

async def checkin(user_id: int) -> bool:
    pool = get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            """UPDATE users
                  SET credits = credits + $1, last_checkin = NOW()
                WHERE user_id = $2
                  AND (last_checkin IS NULL OR last_checkin::date < CURRENT_DATE)
            RETURNING credits""",
            config.CHECKIN_REWARD, user_id,
        )
        return row is not None


# ════════════════════════════════════════════════
# Verifications
# ════════════════════════════════════════════════

async def log_verification_start(user_id: int, service: str, url: str) -> int:
    pool = get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "INSERT INTO verifications (user_id, service, sheerid_url, status) "
            "VALUES ($1, $2, $3, 'pending') RETURNING id",
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
                "UPDATE users SET successful_verifications = successful_verifications + 1 WHERE user_id = $1",
                user_id,
            )


async def admin_stats() -> Dict[str, Any]:
    pool = get_pool()
    async with pool.acquire() as c:
        users_total = await c.fetchval("SELECT COUNT(*) FROM users")
        users_today = await c.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at::date = CURRENT_DATE"
        )
        ver_total = await c.fetchval("SELECT COUNT(*) FROM verifications")
        ver_today = await c.fetchval(
            "SELECT COUNT(*) FROM verifications WHERE created_at::date = CURRENT_DATE"
        )
        ver_success = await c.fetchval(
            "SELECT COUNT(*) FROM verifications WHERE status = 'success'"
        )
        per_service = await c.fetch(
            "SELECT service, COUNT(*) AS n, "
            "COUNT(*) FILTER (WHERE status = 'success') AS ok "
            "FROM verifications GROUP BY service ORDER BY n DESC"
        )
    return {
        "users_total": users_total or 0,
        "users_today": users_today or 0,
        "ver_total": ver_total or 0,
        "ver_today": ver_today or 0,
        "ver_success": ver_success or 0,
        "per_service": [dict(r) for r in per_service],
    }


# ════════════════════════════════════════════════
# Payment Cards (bot2)
# ════════════════════════════════════════════════

async def add_card(
    card_number: str, card_holder: str,
    expiry_month: int, expiry_year: int,
    cvv: str, added_by: int,
) -> Dict[str, Any]:
    pool = get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "INSERT INTO payment_cards "
            "(card_number, card_holder, expiry_month, expiry_year, cvv, added_by) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
            card_number, card_holder, expiry_month, expiry_year, cvv, added_by,
        )
        return dict(row)


async def list_cards(only_unused: bool = False) -> List[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as c:
        if only_unused:
            rows = await c.fetch(
                "SELECT * FROM payment_cards WHERE is_used = FALSE ORDER BY id"
            )
        else:
            rows = await c.fetch("SELECT * FROM payment_cards ORDER BY id")
        return [dict(r) for r in rows]


async def get_next_card() -> Optional[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT * FROM payment_cards WHERE is_used = FALSE ORDER BY id LIMIT 1"
        )
        return dict(row) if row else None


async def mark_card_used(card_id: int, used_by: int) -> None:
    pool = get_pool()
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE payment_cards SET is_used = TRUE, used_by = $1, used_at = NOW() WHERE id = $2",
            used_by, card_id,
        )


async def delete_card(card_id: int) -> bool:
    pool = get_pool()
    async with pool.acquire() as c:
        result = await c.execute("DELETE FROM payment_cards WHERE id = $1", card_id)
        return result == "DELETE 1"


async def cards_stats() -> Dict[str, int]:
    pool = get_pool()
    async with pool.acquire() as c:
        total = await c.fetchval("SELECT COUNT(*) FROM payment_cards") or 0
        unused = await c.fetchval(
            "SELECT COUNT(*) FROM payment_cards WHERE is_used = FALSE"
        ) or 0
        used = await c.fetchval(
            "SELECT COUNT(*) FROM payment_cards WHERE is_used = TRUE"
        ) or 0
    return {"total": total, "unused": unused, "used": used}


# ════════════════════════════════════════════════
# Card Keys / Redeem Codes (bot1)
# ════════════════════════════════════════════════

async def create_card_key(
    key_code: str, credits: int, created_by: int,
    max_uses: int = 1, expire_days: Optional[int] = None,
) -> bool:
    pool = get_pool()
    async with pool.acquire() as c:
        try:
            if expire_days:
                await c.execute(
                    "INSERT INTO card_keys (key_code, credits, max_uses, created_by, expire_at) "
                    "VALUES ($1, $2, $3, $4, NOW() + make_interval(days => $5))",
                    key_code, credits, max_uses, created_by, expire_days,
                )
            else:
                await c.execute(
                    "INSERT INTO card_keys (key_code, credits, max_uses, created_by) "
                    "VALUES ($1, $2, $3, $4)",
                    key_code, credits, max_uses, created_by,
                )
            return True
        except Exception:
            return False


async def use_card_key(key_code: str, user_id: int) -> Optional[int]:
    """Use a card key. Returns credits gained, or negative codes for errors:
    None = not found, -1 = exhausted, -2 = expired, -3 = already used by this user.
    """
    pool = get_pool()
    async with pool.acquire() as c:
        card = await c.fetchrow("SELECT * FROM card_keys WHERE key_code = $1", key_code)
        if not card:
            return None

        if card["expire_at"] and card["expire_at"].replace(tzinfo=None) < __import__("datetime").datetime.utcnow():
            return -2

        if card["current_uses"] >= card["max_uses"]:
            return -1

        already = await c.fetchval(
            "SELECT COUNT(*) FROM card_key_usage WHERE key_code = $1 AND user_id = $2",
            key_code, user_id,
        )
        if already and already > 0:
            return -3

        await c.execute(
            "UPDATE card_keys SET current_uses = current_uses + 1 WHERE key_code = $1",
            key_code,
        )
        await c.execute(
            "INSERT INTO card_key_usage (key_code, user_id) VALUES ($1, $2)",
            key_code, user_id,
        )
        await c.execute(
            "UPDATE users SET credits = credits + $1 WHERE user_id = $2",
            card["credits"], user_id,
        )
        return int(card["credits"])


async def get_all_card_keys() -> List[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as c:
        rows = await c.fetch("SELECT * FROM card_keys ORDER BY created_at DESC")
        return [dict(r) for r in rows]


# ════════════════════════════════════════════════
# Google Cookies
# ════════════════════════════════════════════════

async def save_google_cookies(gmail: str, cookies: list, user_agent: str = "") -> None:
    import json
    pool = get_pool()
    async with pool.acquire() as c:
        await c.execute(
            """INSERT INTO google_cookies (gmail, cookies, user_agent, updated_at)
               VALUES ($1, $2::jsonb, $3, NOW())
               ON CONFLICT (gmail) DO UPDATE
                  SET cookies = $2::jsonb, user_agent = $3, updated_at = NOW()""",
            gmail, json.dumps(cookies), user_agent,
        )


async def get_google_cookies(gmail: str) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT cookies, user_agent, updated_at FROM google_cookies WHERE gmail = $1",
            gmail,
        )
        if not row:
            return None
        import json
        return {
            "cookies": json.loads(row["cookies"]) if isinstance(row["cookies"], str) else row["cookies"],
            "user_agent": row["user_agent"],
            "updated_at": row["updated_at"],
        }


async def delete_google_cookies(gmail: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as c:
        result = await c.execute("DELETE FROM google_cookies WHERE gmail = $1", gmail)
        return result == "DELETE 1"
