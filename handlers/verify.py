"""معالجة رسائل الروابط وتنفيذ التحقق."""
from __future__ import annotations

import asyncio
import html
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.db import models
from bot.services import (
    SERVICE_REGISTRY, detect_service_from_url, extract_sheerid_url, run_verification,
)
from bot.utils.keyboards import back_menu, main_menu

log = logging.getLogger(__name__)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return
    user = update.effective_user

    # تحقّق من الحظر
    if await models.is_banned(user.id):
        await msg.reply_text("🚫 حسابك محظور.")
        return

    sheerid_url = extract_sheerid_url(msg.text)
    if not sheerid_url:
        await msg.reply_text(
            "ℹ️ أرسل رابط SheerID صحيحاً (يحتوي على `sheerid.com`) أو اضغط /start.",
        )
        return

    # تحديد الخدمة: من الزر السابق أو كشف تلقائي من الرابط
    service_key = ctx.user_data.pop("pending_service", None) \
        or detect_service_from_url(sheerid_url)

    if not service_key:
        await msg.reply_text(
            "❓ تعذّر كشف نوع الخدمة من الرابط.\n"
            "اختر الخدمة المناسبة من القائمة:",
            reply_markup=main_menu(),
        )
        return

    meta = SERVICE_REGISTRY[service_key]

    # تحقّق من الرصيد
    row = await models.get_user(user.id)
    if not row:
        row = await models.upsert_user(user.id, user.username, user.first_name)
    if int(row.get("credits", 0)) <= 0:
        await msg.reply_text(
            "💸 رصيدك = 0\n\n"
            "ادعُ أصدقاءك للحصول على رصيد مجاني، أو تواصل مع الإدارة.",
            reply_markup=main_menu(),
        )
        return

    # خصم النقطة
    if not await models.deduct_credit(user.id):
        await msg.reply_text("💸 لا يوجد رصيد كافٍ.")
        return

    ver_id = await models.log_verification_start(user.id, service_key, sheerid_url)

    progress = await msg.reply_text(
        f"⏳ <b>{html.escape(meta['label'])}</b>\n"
        f"جاري التحقق… قد تستغرق العملية حتى 3 دقائق.",
        parse_mode="HTML",
    )

    # تحديثات لطيفة بينما يعمل السكربت
    async def tick():
        steps = ["🔄 توليد الهوية…", "🏫 اختيار المؤسسة…", "📤 رفع المستند…", "🔍 التحقق النهائي…"]
        i = 0
        while True:
            await asyncio.sleep(15)
            try:
                await progress.edit_text(
                    f"⏳ <b>{html.escape(meta['label'])}</b>\n{steps[i % len(steps)]}",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            i += 1

    ticker = asyncio.create_task(tick())
    try:
        result = await run_verification(service_key, sheerid_url, timeout=240)
    finally:
        ticker.cancel()

    await models.log_verification_finish(
        ver_id, user.id, success=result.success, error=result.error,
    )

    # لو فشلت → ارجاع النقطة
    if not result.success:
        await models.add_credits(user.id, 1)

    icon = "✅" if result.success else "❌"
    status = "نجح التحقق" if result.success else "فشل التحقق (تم إرجاع رصيدك)"
    output = html.escape(result.output[-1500:] if result.output else "(لا توجد مخرجات)")

    final_text = (
        f"{icon} <b>{status}</b>\n"
        f"الخدمة: {html.escape(meta['label'])}\n\n"
        f"<pre>{output}</pre>"
    )
    try:
        await progress.edit_text(final_text, parse_mode="HTML", reply_markup=main_menu())
    except Exception:
        await msg.reply_text(final_text, parse_mode="HTML", reply_markup=main_menu())
