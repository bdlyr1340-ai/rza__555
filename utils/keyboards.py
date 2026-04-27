"""لوحات الأزرار التفاعلية."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.services import SERVICE_REGISTRY


def main_menu() -> InlineKeyboardMarkup:
    """قائمة الخدمات الرئيسية."""
    rows = []
    row = []
    for key, meta in SERVICE_REGISTRY.items():
        row.append(InlineKeyboardButton(meta["label"], callback_data=f"svc:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton("👤 حسابي", callback_data="me"),
        InlineKeyboardButton("🎁 دعوة أصدقاء", callback_data="ref"),
    ])
    rows.append([InlineKeyboardButton("ℹ️ مساعدة", callback_data="help")])
    return InlineKeyboardMarkup(rows)


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع للقائمة", callback_data="back")]
    ])
