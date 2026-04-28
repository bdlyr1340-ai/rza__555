"""Inline keyboard layouts."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.services import SERVICE_REGISTRY


def main_menu() -> InlineKeyboardMarkup:
    rows = []
    keys = list(SERVICE_REGISTRY.keys())
    for i in range(0, len(keys), 2):
        pair = keys[i : i + 2]
        row = [
            InlineKeyboardButton(SERVICE_REGISTRY[k]["label"], callback_data=f"svc:{k}")
            for k in pair
        ]
        rows.append(row)
    rows.append([
        InlineKeyboardButton("👤 حسابي", callback_data="me"),
        InlineKeyboardButton("🎁 دعوة", callback_data="ref"),
    ])
    rows.append([
        InlineKeyboardButton("📅 تسجيل حضور", callback_data="checkin"),
        InlineKeyboardButton("🔑 كود تفعيل", callback_data="usekey"),
    ])
    rows.append([InlineKeyboardButton("📖 المساعدة", callback_data="help")])
    return InlineKeyboardMarkup(rows)


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ رجوع", callback_data="back")]]
    )
