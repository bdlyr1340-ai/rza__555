"""معالجة رسائل الروابط وتسجيلها في قاعدة البيانات."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.db import models
from bot.services import SERVICE_REGISTRY, detect_service_from_url, extract_sheerid_url
from bot.utils.keyboards import back_menu, main_menu

log = logging.getLogger(__name__)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text:
        return
    user = update.effective_user

    if await models.is_banned(user.id):
        await msg.reply_text("🚫 حسابك محظور.")
        return

    url = extract_sheerid_url(msg.text)
    if not url:
        await msg.reply_text("ℹ️ أرسل الرابط الصحيح أو اضغط /start حتى تظهر الأزرار.", reply_markup=main_menu())
        return

    service_key = ctx.user_data.pop("pending_service", None) or detect_service_from_url(url)
    if not service_key or service_key not in SERVICE_REGISTRY:
        await msg.reply_text("❓ ما گدرت أحدد نوع الخدمة من الرابط. اختار الخدمة من القائمة:", reply_markup=main_menu())
        return

    row = await models.get_user(user.id)
    if not row:
        row = await models.upsert_user(user.id, user.username, user.first_name)

    ver_id = await models.log_verification_start(user.id, service_key, url)
    meta = SERVICE_REGISTRY[service_key]

    await msg.reply_text(
        "✅ تم استلام الرابط وتسجيل الطلب بقاعدة البيانات.\n\n"
        f"الخدمة: {meta['label']}\n"
        f"رقم الطلب: {ver_id}\n"
        "الرصيد لم يتم خصمه.\n\n"
        "الأزرار والحساب وقاعدة البيانات تعمل بدون انهيار.",
        reply_markup=main_menu(),
    )

    # إشعار الأدمن، بدون كسر البوت إذا فشل الإرسال
    admin_text = (
        "📥 طلب جديد\n\n"
        f"المستخدم: {user.id}\n"
        f"اليوزر: @{user.username or '-'}\n"
        f"الخدمة: {meta['label']}\n"
        f"رقم الطلب: {ver_id}\n"
        f"الرابط:\n{url}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id, admin_text)
        except Exception as e:
            log.warning("Failed to notify admin %s: %s", admin_id, e)
