"""Merged verification handler — URL-based + command-based + Gemini auto."""
from __future__ import annotations

import asyncio
import logging
import re

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.db import models
from bot.services import SERVICE_REGISTRY, detect_service_from_url, extract_sheerid_url
from bot.services.sheerid import run_verification, verify_gemini_auto
from bot.utils.keyboards import back_menu, main_menu

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════
# Gemini auto-flow (credentials conversation)
# ════════════════════════════════════════════════

async def _run_gemini_flow(msg, ctx, user) -> None:
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
            user_id=user.id,
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
            "🎉 *تم التحقق بنجاح!*\n\n"
            f"📧 Gmail: `{result.get('gmail', '—')}`\n"
            f"👤 الشخص: `{result.get('student', '—')}`\n"
            f"🎓 الجامعة: `{result.get('school', '—')}`\n"
            f"📩 إيميل التحقق: `{result.get('email', '—')}`\n"
            f"🔗 رقم التحقق: `{result.get('verificationId', '—')}`\n"
            f"\nحالة SheerID: {sheerid_step}\n"
        )
        await progress_msg.edit_text(reply, parse_mode="Markdown", reply_markup=main_menu())
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
    admin_text = (
        "📥 طلب تحقق جديد (تلقائي)\n\n"
        f"المستخدم: {user.id}\n"
        f"اليوزر: @{user.username or '-'}\n"
        f"الخدمة: {meta['label']}\n"
        f"رقم الطلب: {ver_id}\n"
        f"النتيجة: {'نجاح ✅' if result.get('success') else 'فشل ❌'}\n"
        f"{extra_lines}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id, admin_text)
        except Exception as e:
            log.warning("Failed to notify admin %s: %s", admin_id, e)


# ════════════════════════════════════════════════
# Text message handler (URL-based + Gemini creds)
# ════════════════════════════════════════════════

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text:
        return
    user = update.effective_user

    if await models.is_banned(user.id):
        await msg.reply_text("🚫 حسابك محظور.")
        return

    from bot.handlers.admin import on_admin_card_text
    if await on_admin_card_text(update, ctx):
        return

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
                f"✅ الإيميل: `{text}`\n\n🔑 *الخطوة 2/3:* أرسل كلمة مرور حساب Google:",
                parse_mode="Markdown",
            )
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
                "المفتاح يكون نص مثل: `JBSWY3DPEHPK3PXP`\n\n"
                "_إذا ما عندك 2FA أرسل: skip_",
                parse_mode="Markdown",
            )
            try:
                await msg.delete()
            except Exception:
                pass
            return

        if gemini_step == "2fa":
            totp_secret = text.strip() if text.lower() != "skip" else ""
            ctx.user_data["gemini_2fa"] = totp_secret
            try:
                await msg.delete()
            except Exception:
                pass
            await _run_gemini_flow(msg, ctx, user)
            return

    url = extract_sheerid_url(msg.text)
    if not url:
        await msg.reply_text(
            "ℹ️ أرسل الرابط الصحيح أو اضغط /start.",
            reply_markup=main_menu(),
        )
        return

    pending = ctx.user_data.pop("pending_service", None)
    url_service = detect_service_from_url(url)
    service_key = pending or url_service
    if not service_key or service_key not in SERVICE_REGISTRY:
        await msg.reply_text(
            "❓ ما گدرت أحدد نوع الخدمة. اختار من القائمة:",
            reply_markup=main_menu(),
        )
        return

    row = await models.get_user(user.id)
    if not row:
        row = await models.upsert_user(user.id, user.username, user.first_name)

    if row["credits"] <= 0:
        await msg.reply_text(
            "⚠️ رصيدك منتهي! ادعُ أصدقاء عبر /ref.",
            reply_markup=back_menu(),
        )
        return

    if not await models.deduct_credit(user.id):
        await msg.reply_text("⚠️ لم يتم خصم الرصيد.", reply_markup=back_menu())
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
        log.exception("Verification crashed ver_id=%s", ver_id)
        await models.log_verification_finish(ver_id, user.id, success=False, error=str(exc))
        await models.add_credits(user.id, 1)
        await msg.reply_text(
            f"❌ حدث خطأ:\n{exc}\n\nتم إرجاع الرصيد.",
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
        code = result.get("rewardCode")
        if code:
            reply += f"🎁 كود التفعيل: `{code}`\n"
        reply += f"\nالحالة: {result.get('step', 'pending')}\n"
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


# ════════════════════════════════════════════════
# Command-based verifications (from bot1)
# ════════════════════════════════════════════════

async def _cmd_verify_generic(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE,
    service_key: str, label: str,
) -> None:
    user = update.effective_user
    if await models.is_banned(user.id):
        await update.effective_message.reply_text("🚫 حسابك محظور.")
        return

    row = await models.get_user(user.id)
    if not row:
        await update.effective_message.reply_text("اضغط /start أولاً.")
        return

    args = ctx.args or []
    if not args:
        await update.effective_message.reply_text(
            f"الاستخدام: /{update.effective_message.text.split()[0].lstrip('/')} <رابط SheerID>\n\n"
            f"الخدمة: {label}"
        )
        return

    url = args[0]
    if row["credits"] < config.VERIFY_COST:
        await update.effective_message.reply_text(
            f"⚠️ رصيدك غير كافٍ! تحتاج {config.VERIFY_COST}، رصيدك {row['credits']}.\n"
            "ادعُ أصدقاء /ref أو استخدم كود /use"
        )
        return

    if not await models.deduct_credit(user.id, config.VERIFY_COST):
        await update.effective_message.reply_text("⚠️ فشل خصم الرصيد.")
        return

    ver_id = await models.log_verification_start(user.id, service_key, url)

    processing_msg = await update.effective_message.reply_text(
        f"⏳ جاري معالجة {label}...\n"
        f"تم خصم {config.VERIFY_COST} رصيد\n\nانتظر قليلاً..."
    )

    try:
        result = await run_verification(service_key, url)
    except Exception as exc:
        log.exception("Verification error for %s", service_key)
        await models.log_verification_finish(ver_id, user.id, success=False, error=str(exc))
        await models.add_credits(user.id, config.VERIFY_COST)
        await processing_msg.edit_text(
            f"❌ خطأ: {exc}\n\nتم إرجاع الرصيد."
        )
        return

    if result.get("success"):
        await models.log_verification_finish(ver_id, user.id, success=True)
        result_msg = f"✅ {label} — نجاح!\n\n"
        if result.get("pending"):
            result_msg += "تم تقديم المستندات، بانتظار المراجعة.\n"
        code = result.get("rewardCode")
        if code:
            result_msg += f"🎁 كود التفعيل: `{code}`\n"
        if result.get("redirect_url"):
            result_msg += f"🔗 الرابط:\n{result['redirect_url']}"
        await processing_msg.edit_text(result_msg, parse_mode="Markdown")
    else:
        await models.log_verification_finish(
            ver_id, user.id, success=False, error=result.get("error")
        )
        await models.add_credits(user.id, config.VERIFY_COST)
        await processing_msg.edit_text(
            f"❌ فشل: {result.get('error', result.get('message', 'خطأ غير معروف'))}\n\nتم إرجاع الرصيد."
        )

    admin_text = (
        f"📥 تحقق ({label})\n"
        f"المستخدم: {user.id} @{user.username or '-'}\n"
        f"النتيجة: {'✅' if result.get('success') else '❌'}\n"
        f"الرابط: {url}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id, admin_text)
        except Exception:
            pass


async def cmd_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _cmd_verify_generic(update, ctx, "google_one", "Google One / Gemini")


async def cmd_verify2(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _cmd_verify_generic(update, ctx, "k12", "ChatGPT Teacher K12")


async def cmd_verify3(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _cmd_verify_generic(update, ctx, "spotify", "Spotify Student")


async def cmd_verify4(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _cmd_verify_generic(update, ctx, "boltnew", "Bolt.new Teacher")


async def cmd_verify5(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _cmd_verify_generic(update, ctx, "youtube", "YouTube Student")


# ════════════════════════════════════════════════
# /getV4Code — check Bolt.new reward code
# ════════════════════════════════════════════════

async def cmd_getV4Code(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await models.is_banned(user.id):
        await update.effective_message.reply_text("🚫 حسابك محظور.")
        return

    args = ctx.args or []
    if not args:
        await update.effective_message.reply_text(
            "الاستخدام: /getV4Code <verification_id>\n\n"
            "مثال: /getV4Code 6929436b50d7dc18638890d0"
        )
        return

    verification_id = args[0].strip()
    processing_msg = await update.effective_message.reply_text("🔍 جاري البحث عن الكود...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://my.sheerid.com/rest/v2/verification/{verification_id}"
            )
            if response.status_code != 200:
                await processing_msg.edit_text(f"❌ فشل الاستعلام (HTTP {response.status_code}).")
                return

            data = response.json()
            current_step = data.get("currentStep")
            reward_code = data.get("rewardCode") or data.get("rewardData", {}).get("rewardCode")
            redirect_url = data.get("redirectUrl")

            if current_step == "success" and reward_code:
                text = f"✅ تم!\n\n🎁 الكود: `{reward_code}`\n"
                if redirect_url:
                    text += f"\n🔗 {redirect_url}"
                await processing_msg.edit_text(text, parse_mode="Markdown")
            elif current_step == "pending":
                await processing_msg.edit_text("⏳ لا يزال قيد المراجعة. حاول لاحقاً.")
            elif current_step == "error":
                errors = data.get("errorIds", [])
                await processing_msg.edit_text(
                    f"❌ فشل التحقق\n{', '.join(errors) if errors else 'خطأ غير معروف'}"
                )
            else:
                await processing_msg.edit_text(f"⚠️ الحالة: {current_step}\nحاول لاحقاً.")

    except Exception as e:
        log.error("getV4Code error: %s", e)
        await processing_msg.edit_text(f"❌ خطأ: {e}")
