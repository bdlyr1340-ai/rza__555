"""Text/link handler."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.db import models
from bot.services import SERVICE_REGISTRY, detect_service_from_url, extract_sheerid_url
from bot.utils.keyboards import main_menu


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text:
        return
    user = update.effective_user

    if await models.is_banned(user.id):
        await msg.reply_text("🚫 حسابك محظور.")
        return

    sheerid_url = extract_sheerid_url(msg.text)
    if not sheerid_url:
        await msg.reply_text("اكتب /start حتى تظهر الأزرار.", reply_markup=main_menu())
        return

    service_key = ctx.user_data.pop("pending_service", None) or detect_service_from_url(sheerid_url)
    if not service_key or service_key not in SERVICE_REGISTRY:
        await msg.reply_text("اختر الخدمة المناسبة من القائمة:", reply_markup=main_menu())
        return

    row = await models.get_user(user.id)
    if not row:
        row = await models.upsert_user(user.id, user.username, user.first_name)

    await models.log_verification_start(user.id, service_key, sheerid_url)
    await msg.reply_text(
        "✅ وصلت الرسالة وتم تسجيلها.\n\n"
        "الأزرار والحساب وقاعدة البيانات شغالة.\n"
        "تشغيل التحقق التلقائي عبر خدمات طرف ثالث غير مفعّل في هذه النسخة.",
        reply_markup=main_menu(),
    )
