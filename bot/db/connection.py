"""PostgreSQL connection using asyncpg."""
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

    log.info("Connecting to PostgreSQL...")
    _pool = await asyncpg.create_pool(
        dsn=config.DATABASE_URL,
        min_size=1,
        max_size=5,
        command_timeout=30,
    )

    sql = (Path(__file__).parent / "migrations.sql").read_text(encoding="utf-8")
    async with _pool.acquire() as conn:
        await conn.execute(sql)

    log.info("Database ready.")
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
