"""تحميل إعدادات البوت من المتغيرات البيئية."""
import os
from typing import List


def _parse_admin_ids(raw: str) -> List[int]:
    if not raw:
        return []
    out = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


# ===== Telegram =====
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS: List[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

# ===== Database (Railway يُولّد DATABASE_URL تلقائياً) =====
DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

# ===== Credits =====
DEFAULT_CREDITS: int = int(os.getenv("DEFAULT_CREDITS", "3"))
REFERRAL_BONUS: int = int(os.getenv("REFERRAL_BONUS", "5"))

# ===== Misc =====
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


def validate() -> None:
    """يتحقق من توفر المتغيرات الإلزامية."""
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if missing:
        raise SystemExit(
            "❌ المتغيرات البيئية التالية مفقودة: " + ", ".join(missing)
            + "\nراجع .env.example"
        )
