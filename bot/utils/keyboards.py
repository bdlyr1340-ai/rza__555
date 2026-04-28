"""لوحات الأزرار التفاعلية."""
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot import config
from bot.services import SERVICE_REGISTRY


def main_menu(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
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
        InlineKeyboardButton("🎁 رابط الدعوة", callback_data="ref"),
    ])
    rows.append([InlineKeyboardButton("ℹ️ المساعدة", callback_data="help")])

    if user_id and user_id in config.ADMIN_IDS:
        rows.append([InlineKeyboardButton("🛠 لوحة التحكم", callback_data="admin_panel")])

    return InlineKeyboardMarkup(rows)


def admin_panel_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin:stats")],
        [InlineKeyboardButton("💳 البطاقات", callback_data="admin:cards")],
        [InlineKeyboardButton("➕ إضافة بطاقة", callback_data="admin:addcard")],
        [InlineKeyboardButton("👥 إضافة رصيد", callback_data="admin:addcredit")],
        [InlineKeyboardButton("📣 رسالة جماعية", callback_data="admin:broadcast")],
        [InlineKeyboardButton("⬅️ رجوع للقائمة", callback_data="back")],
    ])


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع للقائمة", callback_data="back")]
    ])
