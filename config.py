from __future__ import annotations

import os
from typing import List


def _parse_admin_ids(value: str) -> List[int]:
    ids: List[int] = []
    for part in (value or "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    return ids


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = _first_env(
    "DATABASE_URL",
    "POSTGRES_URL",
    "DATABASE_PRIVATE_URL",
    "POSTGRES_PRIVATE_URL",
)
ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
DEFAULT_CREDITS = _int_env("DEFAULT_CREDITS", 3)
REFERRAL_BONUS = _int_env("REFERRAL_BONUS", 5)
PORT = _int_env("PORT", 8080)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"


def validate() -> None:
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))
