"""Merged bot configuration — all values from environment variables."""
from __future__ import annotations

import os
import sys


def _int_list(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


# ── Telegram ──
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS: list[int] = _int_list(os.environ.get("ADMIN_IDS", ""))
CHANNEL_USERNAME: str = os.environ.get("CHANNEL_USERNAME", "")
CHANNEL_URL: str = os.environ.get("CHANNEL_URL", "")

# ── Database (PostgreSQL on Railway) ──
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

# ── Credits / Points ──
DEFAULT_CREDITS: int = int(os.environ.get("DEFAULT_CREDITS", "3"))
VERIFY_COST: int = int(os.environ.get("VERIFY_COST", "1"))
CHECKIN_REWARD: int = int(os.environ.get("CHECKIN_REWARD", "1"))
REFERRAL_BONUS: int = int(os.environ.get("REFERRAL_BONUS", "2"))
REGISTER_REWARD: int = int(os.environ.get("REGISTER_REWARD", "1"))

# ── Proxy ──
PROXY_URL: str = os.environ.get("PROXY_URL", "")
PROXY_LIST: str = os.environ.get("PROXY_LIST", "")

# ── Cloud Browser (BrowserBase / Browserless) ──
# Set BROWSER_PROVIDER to "browserbase" or "browserless" to use cloud browsers
# instead of local Chromium. Falls back to local if not set.
BROWSER_PROVIDER: str = os.environ.get("BROWSER_PROVIDER", "")  # "browserbase" | "browserless" | ""
BROWSERBASE_API_KEY: str = os.environ.get("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID: str = os.environ.get("BROWSERBASE_PROJECT_ID", "")
BROWSERLESS_TOKEN: str = os.environ.get("BROWSERLESS_TOKEN", "")
BROWSERLESS_URL: str = os.environ.get("BROWSERLESS_URL", "wss://chrome.browserless.io")

# ── WebApp ──
WEBAPP_URL: str = os.environ.get("WEBAPP_URL", "https://webapp-amfovjji.devinapps.com")

# ── Logging ──
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

# ── Help ──
HELP_NOTION_URL: str = os.environ.get(
    "HELP_NOTION_URL",
    "https://rhetorical-era-3f3.notion.site/dd78531dbac745af9bbac156b51da9cc",
)


def validate() -> None:
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if not ADMIN_IDS:
        missing.append("ADMIN_IDS")
    if missing:
        print(f"[FATAL] Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
