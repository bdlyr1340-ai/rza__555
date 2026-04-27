"""اتصال PostgreSQL باستخدام asyncpg + تشغيل المهاجرات."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import asyncpg

from bot import config

log = logging.getLogger(__name__)
_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool

    log.info("Connecting to database...")
    _pool = await asyncpg.create_pool(
        dsn=config.DATABASE_URL,
        min_size=1,
        max_size=5,
        command_timeout=30,
    )

    sql = (Path(__file__).parent / "migrations.sql").read_text(encoding="utf-8")
    async with _pool.acquire() as conn:
        for idx, statement in enumerate(sql.split(";")):
            lines = [l for l in statement.splitlines() if not l.strip().startswith("--")]
            cleaned = "\n".join(lines).strip()
            if cleaned:
                try:
                    await conn.execute(cleaned)
                except Exception as exc:
                    log.error("Migration statement %d failed: %s\n  SQL: %s", idx, exc, cleaned[:120])
                    raise
    log.info("Database is ready.")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised yet")
    return _pool
