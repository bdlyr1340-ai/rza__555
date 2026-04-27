"""معالجة رسائل الروابط وتشغيل التحقق الفعلي عبر SheerID."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.db import models
from bot.services import SERVICE_REGISTRY, detect_service_from_url, extract_sheerid_url
from bot.services.sheerid import run_verification
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
        await msg.reply_text(
            "ℹ️ أرسل الرابط الصحيح أو اضغط /start حتى تظهر الأزرار.",
            reply_markup=main_menu(),
        )
        return

    service_key = ctx.user_data.pop("pending_service", None) or detect_service_from_url(url)
    if not service_key or service_key not in SERVICE_REGISTRY:
        await msg.reply_text(
            "❓ ما گدرت أحدد نوع الخدمة من الرابط. اختار الخدمة من القائمة:",
            reply_markup=main_menu(),
        )
        return

    row = await models.get_user(user.id)
    if not row:
        row = await models.upsert_user(user.id, user.username, user.first_name)

    if row["credits"] <= 0:
        await msg.reply_text(
            "⚠️ رصيدك منتهي! ادعُ أصدقاء عبر /ref حتى تحصل على رصيد إضافي.",
            reply_markup=back_menu(),
        )
        return

    if not await models.deduct_credit(user.id):
        await msg.reply_text("⚠️ لم يتم خصم الرصيد، حاول مرة ثانية.", reply_markup=back_menu())
        return

    meta = SERVICE_REGISTRY[service_key]
    ver_id = await models.log_verification_start(user.id, service_key, url)

    await msg.reply_text(
        f"⏳ جاري التحقق...\n\nالخدمة: {meta['label']}\nرقم الطلب: {ver_id}\n\nانتظر قليلاً...",
        reply_markup=back_menu(),
    )

    try:
        result = await run_verification(service_key, url)
    except Exception as exc:
        log.exception("Verification crashed for ver_id=%s", ver_id)
        await models.log_verification_finish(ver_id, user.id, success=False, error=str(exc))
        await models.add_credits(user.id, 1)
        await msg.reply_text(
            f"❌ حدث خطأ أثناء التحقق:\n{exc}\n\nتم إرجاع الرصيد.",
            reply_markup=main_menu(),
        )
        return

    if result.get("success"):
        await models.log_verification_finish(ver_id, user.id, success=True)
        person = result.get("student") or result.get("teacher") or result.get("person", "—")
        reply = (
            "🎉 *تم التحقق بنجاح!*\n\n"
            f"الخدمة: {meta['label']}\n"
            f"الشخص: `{person}`\n"
            f"الإيميل: `{result.get('email', '—')}`\n"
        )
        school = result.get("school")
        if school:
            reply += f"الجامعة/المدرسة: {school}\n"
        reply += f"\nالحالة: {result.get('step', 'pending')}\n"
        reply += "\n⏳ انتظر 24-48 ساعة للمراجعة."
        await msg.reply_markdown(reply, reply_markup=main_menu())
    else:
        await models.log_verification_finish(ver_id, user.id, success=False, error=result.get("error"))
        await models.add_credits(user.id, 1)
        await msg.reply_text(
            f"❌ فشل التحقق:\n{result.get('error', 'خطأ غير معروف')}\n\nتم إرجاع الرصيد.",
            reply_markup=main_menu(),
        )

    admin_text = (
        "📥 طلب تحقق جديد\n\n"
        f"المستخدم: {user.id}\n"
        f"اليوزر: @{user.username or '-'}\n"
        f"الخدمة: {meta['label']}\n"
        f"رقم الطلب: {ver_id}\n"
        f"النتيجة: {'نجاح ✅' if result.get('success') else 'فشل ❌'}\n"
        f"الرابط:\n{url}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id, admin_text)
        except Exception as e:
            log.warning("Failed to notify admin %s: %s", admin_id, e)
