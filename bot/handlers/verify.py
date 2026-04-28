"""معالجة رسائل الروابط وتشغيل التحقق الفعلي عبر SheerID."""
from __future__ import annotations

import asyncio
import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.db import models
from bot.services import SERVICE_REGISTRY, detect_service_from_url, extract_sheerid_url
from bot.services.sheerid import run_verification, verify_gemini_auto, poll_sheerid_until_approved, claim_google_offer
from bot.utils.keyboards import back_menu, main_menu

log = logging.getLogger(__name__)


async def _background_sheerid_poll(
    bot, user_id: int, username: str, ver_id: int, vid: str,
    gmail: str, gmail_password: str, totp_secret: str,
    result_info: dict,
) -> None:
    """Background task: poll SheerID, claim offer on approval, notify user."""
    try:
        poll_result = await poll_sheerid_until_approved(vid, max_minutes=30, poll_interval=30)

        if poll_result.get("approved"):
            redirect_url = poll_result["redirect_url"]
            log.info("BG: SheerID approved vid=%s, claiming offer...", vid[:12])

            # Claim the Google offer
            claim_result = await claim_google_offer(gmail, gmail_password, totp_secret, redirect_url)

            if claim_result.get("claimed"):
                await models.log_verification_finish(ver_id, user_id, success=True)
                await bot.send_message(
                    user_id,
                    "🎉 *تهانياً تم تفعيل جيمناي برو سنوي!*\n\n"
                    f"📧 Gmail: `{gmail}`\n"
                    f"👤 الشخص: `{result_info.get('student', '—')}`\n"
                    f"🎓 الجامعة: `{result_info.get('school', '—')}`\n"
                    f"🔗 رقم التحقق: `{vid}`\n\n"
                    "✅ تم التفعيل بنجاح!",
                    parse_mode="Markdown",
                )
            else:
                await models.log_verification_finish(ver_id, user_id, success=True)
                await bot.send_message(
                    user_id,
                    "✅ *SheerID وافق على التحقق!*\n\n"
                    f"🔗 رابط العرض:\n`{redirect_url}`\n\n"
                    "افتح الرابط في المتصفح لتفعيل العرض يدوياً.",
                    parse_mode="Markdown",
                )
        else:
            # SheerID rejected or timed out
            await models.log_verification_finish(ver_id, user_id, success=False, error=poll_result.get("error"))
            await models.add_credits(user_id, 1)
            await bot.send_message(
                user_id,
                f"❌ *فشل التحقق:*\n{poll_result.get('error', 'خطأ غير معروف')}\n\n"
                "تم إرجاع الرصيد.",
                parse_mode="Markdown",
            )

        # Notify admins
        extra = f"حالة SheerID: {poll_result.get('step', '—')}\nرقم التحقق: {vid}\n"
        admin_text = (
            "📥 نتيجة تحقق (خلفي)\n\n"
            f"المستخدم: {user_id}\n"
            f"اليوزر: @{username or '-'}\n"
            f"الخدمة: 🤖 جوجل ون / جيمناي\n"
            f"رقم الطلب: {ver_id}\n"
            f"النتيجة: {'نجاح ✅' if poll_result.get('approved') else 'فشل ❌'}\n"
            f"{extra}"
        )
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text)
            except Exception as e:
                log.warning("Failed to notify admin %s: %s", admin_id, e)

    except Exception as exc:
        log.exception("Background SheerID poll crashed: %s", exc)
        await models.log_verification_finish(ver_id, user_id, success=False, error=str(exc))
        await models.add_credits(user_id, 1)
        try:
            await bot.send_message(
                user_id,
                f"❌ حدث خطأ أثناء المراجعة:\n{exc}\n\nتم إرجاع الرصيد.",
            )
        except Exception:
            pass


async def _run_gemini_flow(msg, ctx, user) -> None:
    """Execute the full Gemini auto-verification after all credentials collected."""
    gmail = ctx.user_data.pop("gemini_email", "")
    gmail_password = ctx.user_data.pop("gemini_password", "")
    totp_secret = ctx.user_data.pop("gemini_2fa", "")
    ctx.user_data.pop("gemini_flow", None)

    meta = SERVICE_REGISTRY["google_one"]

    if not await models.deduct_credit(user.id):
        await msg.reply_text("⚠️ لم يتم خصم الرصيد.", reply_markup=back_menu())
        return

    ver_id = await models.log_verification_start(user.id, "google_one", "auto-gemini")
    progress_msg = await msg.reply_text("⏳ جاري التحقق التلقائي...\n\n🤖 جوجل ون / جيمناي")

    async def _update_progress(text: str) -> None:
        try:
            await progress_msg.edit_text(f"🤖 *جوجل ون / جيمناي*\n\n{text}", parse_mode="Markdown")
        except Exception:
            pass

    try:
        result = await verify_gemini_auto(
            _update_progress,
            gmail=gmail,
            gmail_password=gmail_password,
            totp_secret=totp_secret,
        )
    except Exception as exc:
        log.exception("Gemini auto crashed ver_id=%s", ver_id)
        await models.log_verification_finish(ver_id, user.id, success=False, error=str(exc))
        await models.add_credits(user.id, 1)
        await progress_msg.edit_text(
            f"❌ حدث خطأ:\n{exc}\n\nتم إرجاع الرصيد.",
            reply_markup=main_menu(),
        )
        return

    if result.get("success"):
        await models.log_verification_finish(ver_id, user.id, success=True)
        sheerid_step = result.get("step", "pending")
        reply = (
            "🎉 *تهانياً تم تفعيل جيمناي برو سنوي!*\n\n"
            f"📧 Gmail: `{result.get('gmail', '—')}`\n"
            f"👤 الشخص: `{result.get('student', '—')}`\n"
            f"🎓 الجامعة: `{result.get('school', '—')}`\n"
            f"📩 إيميل التحقق: `{result.get('email', '—')}`\n"
            f"🔗 رقم التحقق: `{result.get('verificationId', '—')}`\n"
            f"\nحالة SheerID: {sheerid_step}\n"
        )
        await progress_msg.edit_text(reply, parse_mode="Markdown", reply_markup=main_menu())
    elif result.get("pending"):
        # SheerID is reviewing documents — start background polling
        vid = result.get("verificationId", "")
        await progress_msg.edit_text(
            "⏳ *المستندات تحت المراجعة*\n\n"
            "SheerID يراجع المستندات الآن. سيتم إشعارك تلقائياً عند الموافقة.\n"
            f"رقم التحقق: `{vid}`\n\n"
            "⏱ المراجعة قد تستغرق حتى 30 دقيقة.",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        # Start background task
        asyncio.create_task(
            _background_sheerid_poll(
                bot=ctx.bot,
                user_id=user.id,
                username=user.username,
                ver_id=ver_id,
                vid=vid,
                gmail=gmail,
                gmail_password=gmail_password,
                totp_secret=totp_secret,
                result_info=result,
            )
        )
        # Don't refund credits yet — wait for background result
    else:
        await models.log_verification_finish(ver_id, user.id, success=False, error=result.get("error"))
        await models.add_credits(user.id, 1)
        await progress_msg.edit_text(
            f"❌ فشل التحقق:\n{result.get('error', 'خطأ غير معروف')}\n\nتم إرجاع الرصيد.",
            reply_markup=main_menu(),
        )

    extra_lines = ""
    if not result.get("success") and result.get("error"):
        extra_lines += f"السبب: {result['error']}\n"
    if result.get("step"):
        extra_lines += f"حالة SheerID: {result['step']}\n"
    if result.get("verificationId"):
        extra_lines += f"رقم التحقق: {result['verificationId']}\n"
    if result.get("redirect"):
        extra_lines += f"رابط العرض: {result['redirect'][:80]}\n"
    admin_text = (
        "📥 طلب تحقق جديد (تلقائي)\n\n"
        f"المستخدم: {user.id}\n"
        f"اليوزر: @{user.username or '-'}\n"
        f"الخدمة: {meta['label']}\n"
        f"رقم الطلب: {ver_id}\n"
        f"النتيجة: {'نجاح ✅' if result.get('success') else ('قيد المراجعة ⏳' if result.get('pending') else 'فشل ❌')}\n"
        f"{extra_lines}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id, admin_text)
        except Exception as e:
            log.warning("Failed to notify admin %s: %s", admin_id, e)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text:
        return
    user = update.effective_user

    if await models.is_banned(user.id):
        await msg.reply_text("🚫 حسابك محظور.")
        return

    # Handle Gemini conversation flow
    gemini_step = ctx.user_data.get("gemini_flow")
    if gemini_step:
        text = msg.text.strip()

        if gemini_step == "email":
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text):
                await msg.reply_text("❌ إيميل غير صالح. أرسل إيميل Gmail صحيح:")
                return
            ctx.user_data["gemini_email"] = text
            ctx.user_data["gemini_flow"] = "password"
            await msg.reply_text(
                f"✅ الإيميل: `{text}`\n\n"
                "🔑 *الخطوة 2/3:* أرسل كلمة مرور حساب Google:",
                parse_mode="Markdown",
            )
            # Delete the email message for privacy
            try:
                await msg.delete()
            except Exception:
                pass
            return

        if gemini_step == "password":
            ctx.user_data["gemini_password"] = text
            ctx.user_data["gemini_flow"] = "2fa"
            await msg.reply_text(
                "✅ تم حفظ كلمة المرور\n\n"
                "🔐 *الخطوة 3/3:* أرسل مفتاح 2FA السري (Secret Key):\n\n"
                "المفتاح يكون نص مثل: `JBSWY3DPEHPK3PXP`\n"
                "تلاقيه في إعدادات Google Authenticator\n\n"
                "_إذا ما عندك 2FA أرسل: skip_",
                parse_mode="Markdown",
            )
            # Delete the password message for privacy
            try:
                await msg.delete()
            except Exception:
                pass
            return

        if gemini_step == "2fa":
            totp_secret = text.strip() if text.lower() != "skip" else ""
            ctx.user_data["gemini_2fa"] = totp_secret
            # Delete the 2FA message for privacy
            try:
                await msg.delete()
            except Exception:
                pass
            # All credentials collected — run the flow
            await _run_gemini_flow(msg, ctx, user)
            return

    url = extract_sheerid_url(msg.text)
    if not url:
        await msg.reply_text(
            "ℹ️ أرسل الرابط الصحيح أو اضغط /start حتى تظهر الأزرار.",
            reply_markup=main_menu(),
        )
        return

    pending = ctx.user_data.pop("pending_service", None)
    url_service = detect_service_from_url(url)
    service_key = pending or url_service
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
