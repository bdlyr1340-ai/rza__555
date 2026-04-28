"""Merged /start handler, main menu, and button routing."""
from __future__ import annotations

import asyncio
import json
import logging
import time

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    Update, WebAppInfo,
)
from telegram.ext import ContextTypes

from bot import config
from bot.db import models
from bot.services import SERVICE_REGISTRY
from bot.services.sheerid import verify_gemini_auto
from bot.utils.keyboards import back_menu, main_menu

log = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 *أهلاً بيك بالبوت*\n\n"
    "اختر الخدمة المطلوبة من الأزرار بالأسفل.\n\n"
    "💎 *رصيدك الحالي:* `{credits}`\n"
)

HELP_TEXT = (
    "📖 *دليل الاستخدام*\n\n"
    "• اضغط على الخدمة من الأزرار.\n"
    "• أرسل الرابط بعدها برسالة عادية.\n"
    "• البوت يحفظ الطلب ويربطه بحسابك.\n\n"
    "*الأوامر:*\n"
    "/start — القائمة الرئيسية\n"
    "/ping — فحص استجابة البوت\n"
    "/me — حسابي ورصيدي\n"
    "/ref — رابط الدعوة\n"
    "/qd — تسجيل حضور يومي\n"
    "/use `<كود>` — استخدام كود تفعيل\n"
    "/pixel — تفعيل Google One (WebApp)\n"
    "/help — المساعدة\n\n"
    "*أوامر التحقق:*\n"
    "/verify `<رابط>` — Google One / Gemini\n"
    "/verify2 `<رابط>` — ChatGPT K12\n"
    "/verify3 `<رابط>` — Spotify Student\n"
    "/verify4 `<رابط>` — Bolt.new Teacher\n"
    "/verify5 `<رابط>` — YouTube Student\n"
    "/getV4Code `<id>` — كود Bolt.new\n"
)


def _clear_gemini_state(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    for k in ("gemini_flow", "gemini_email", "gemini_password", "gemini_2fa"):
        ctx.user_data.pop(k, None)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    _clear_gemini_state(ctx)
    user = update.effective_user
    args = ctx.args or []

    referred_by = None
    if args and args[0].startswith("ref_") and args[0][4:].isdigit():
        referred_by = int(args[0][4:])
    elif args and args[0].isdigit():
        referred_by = int(args[0])

    row = await models.upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        referred_by=referred_by,
    )
    if row.get("is_banned"):
        await update.effective_message.reply_text("🚫 حسابك محظور من استخدام البوت.")
        return

    await update.effective_message.reply_markdown(
        WELCOME_TEXT.format(credits=row["credits"]),
        reply_markup=main_menu(),
    )


async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("✅ البوت شغال ويستقبل الرسائل.")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    is_admin = update.effective_user.id in config.ADMIN_IDS
    text = HELP_TEXT
    if is_admin:
        text += (
            "\n*أوامر الأدمن:*\n"
            "/admin — لوحة التحكم\n"
            "/stats — الإحصائيات\n"
            "/addcredit `<user_id> <amount>` — إضافة رصيد\n"
            "/ban `<user_id>` — حظر\n"
            "/unban `<user_id>` — رفع الحظر\n"
            "/blacklist — قائمة المحظورين\n"
            "/broadcast `<رسالة>` — بث رسالة\n"
            "/genkey `<كود> <رصيد> [عدد] [أيام]` — إنشاء كود\n"
            "/listkeys — عرض الأكواد\n"
            "/addcard — إضافة بطاقة ائتمان\n"
            "/cards — عرض البطاقات\n"
            "/delcard `<id>` — حذف بطاقة\n"
        )
    await update.effective_message.reply_markdown(text, reply_markup=back_menu())


async def cmd_me(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    row = await models.get_user(user.id)
    if not row:
        row = await models.upsert_user(user.id, user.username, user.first_name)
    text = (
        "👤 *حسابي*\n\n"
        f"• المعرّف: `{row['user_id']}`\n"
        f"• الاسم: {row.get('first_name') or '-'}\n"
        f"• الرصيد: *{row['credits']}*\n"
        f"• إجمالي الطلبات: {row['total_verifications']}\n"
        f"• الناجحة: {row['successful_verifications']}\n"
    )
    await update.effective_message.reply_markdown(text, reply_markup=back_menu())


async def cmd_ref(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    me = await ctx.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{user.id}"
    text = (
        "🎁 *دعوة الأصدقاء*\n\n"
        f"شارك هذا الرابط، وكل صديق يبدأ البوت عبره يمنحك *+{config.REFERRAL_BONUS} رصيد*:\n\n"
        f"`{link}`"
    )
    await update.effective_message.reply_markdown(text, reply_markup=back_menu())


async def cmd_qd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await models.is_banned(user.id):
        await update.effective_message.reply_text("🚫 حسابك محظور.")
        return
    row = await models.get_user(user.id)
    if not row:
        await update.effective_message.reply_text("اضغط /start أولاً.")
        return
    if await models.checkin(user.id):
        row = await models.get_user(user.id)
        await update.effective_message.reply_text(
            f"✅ تم تسجيل الحضور!\n+{config.CHECKIN_REWARD} رصيد\nرصيدك الحالي: {row['credits']}"
        )
    else:
        await update.effective_message.reply_text("❌ سجّلت حضورك اليوم مسبقاً. ارجع بكرة!")


async def cmd_use(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
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
        await update.effective_message.reply_text("الاستخدام: /use <كود التفعيل>")
        return

    key_code = args[0].strip()
    result = await models.use_card_key(key_code, user.id)

    if result is None:
        await update.effective_message.reply_text("❌ الكود غير موجود.")
    elif result == -1:
        await update.effective_message.reply_text("❌ الكود مستنفد (وصل لعدد الاستخدامات).")
    elif result == -2:
        await update.effective_message.reply_text("❌ الكود منتهي الصلاحية.")
    elif result == -3:
        await update.effective_message.reply_text("❌ استخدمت هذا الكود مسبقاً.")
    else:
        row = await models.get_user(user.id)
        await update.effective_message.reply_text(
            f"✅ تم! حصلت على +{result} رصيد.\nرصيدك الحالي: {row['credits']}"
        )


# ────────────── /pixel command ──────────────

async def cmd_pixel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Open the Pixel Automation WebApp for Google One activation."""
    user = update.effective_user
    if await models.is_banned(user.id):
        await update.effective_message.reply_text("🚫 حسابك محظور.")
        return
    row = await models.get_user(user.id)
    if not row:
        row = await models.upsert_user(user.id, user.username, user.first_name)
    if row["credits"] <= 0:
        await update.effective_message.reply_text(
            "⚠️ رصيدك منتهي! ادعُ أصدقاء عبر /ref.",
            reply_markup=back_menu(),
        )
        return
    # Must use KeyboardButton (reply keyboard) for sendData to work
    webapp_kb = ReplyKeyboardMarkup(
        [[KeyboardButton(
            "⚡ فتح نموذج التفعيل",
            web_app=WebAppInfo(url=config.WEBAPP_URL),
        )]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.effective_message.reply_text(
        "🤖 *Google One / Gemini Pro — تفعيل تلقائي*\n\n"
        "اضغط الزر أدناه لإدخال بيانات حساب Google:",
        parse_mode="Markdown",
        reply_markup=webapp_kb,
    )


# ────────────── 10-step progress display ──────────────

_STEP_NAMES = [
    "Email",
    "Spam check",
    "Password",
    "Two-factor auth",
    "Payment method",
    "Add payment",
    "Check offer",
    "Claim offer",
    "Process payment",
    "Complete",
]


def _build_pixel_progress(gmail: str, current_step: int, elapsed_secs: float,
                           success: bool = False, error: str = "") -> str:
    """Build 10-step progress text matching reference bot style."""
    lines = ["🤖 Pixel Automation", f"📧 {gmail}", "────────────────────────"]
    for i, name in enumerate(_STEP_NAMES):
        step_num = i + 1
        if i < current_step:
            icon = "  ✅"
        elif i == current_step and not error:
            icon = "  🔄"
        elif error and i == current_step:
            icon = "  ❌"
        else:
            icon = "  ⬜"
        lines.append(f"{icon} {step_num:>2}. {name}")
    lines.append("────────────────────────")
    if success:
        lines.append("🎉 Success!")
    elif error:
        lines.append(f"❌ {error}")
    mins = int(elapsed_secs) // 60
    secs = int(elapsed_secs) % 60
    lines.append(f"⏱ Elapsed: {mins:02d}:{secs:02d}")
    return "\n".join(lines)


# ────────────── WebApp data handler ──────────────

async def on_webapp_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle data sent from the Telegram WebApp (credential form)."""
    msg = update.effective_message
    user = update.effective_user

    if not msg or not msg.web_app_data:
        return

    try:
        data = json.loads(msg.web_app_data.data)
    except (json.JSONDecodeError, TypeError):
        await msg.reply_text("❌ بيانات غير صالحة من النموذج.")
        return

    if data.get("action") != "pixel_activate":
        return

    gmail = data.get("email", "").strip()
    gmail_password = data.get("password", "")
    totp_secret = data.get("totp", "").strip()

    if not gmail or not gmail_password:
        await msg.reply_text("❌ الإيميل وكلمة المرور مطلوبان.")
        return

    if await models.is_banned(user.id):
        await msg.reply_text("🚫 حسابك محظور.")
        return

    row = await models.get_user(user.id)
    if not row:
        row = await models.upsert_user(user.id, user.username, user.first_name)

    if row["credits"] <= 0:
        await msg.reply_text("⚠️ رصيدك منتهي! ادعُ أصدقاء عبر /ref.", reply_markup=back_menu())
        return

    meta = SERVICE_REGISTRY["google_one"]

    if not await models.deduct_credit(user.id):
        await msg.reply_text("⚠️ لم يتم خصم الرصيد.", reply_markup=back_menu())
        return

    ver_id = await models.log_verification_start(user.id, "google_one", "auto-pixel")
    start_time = time.time()

    # Remove reply keyboard and show progress
    progress_msg = await msg.reply_text(
        _build_pixel_progress(gmail, 0, 0),
        reply_markup=ReplyKeyboardRemove(),
    )

    _current_step = 0

    async def _update_progress(text: str) -> None:
        nonlocal _current_step
        # Map internal progress to 10-step display
        # Internal steps: 0=email, 1=password, 2=2fa, 3=logged_in, 4+=sheerid
        try:
            # Parse internal step from text
            if "تسجيل الدخول" in text or "Email" in text or "الإيميل" in text:
                _current_step = 0
            elif "كلمة السر" in text or "Password" in text or "كلمة المرور" in text:
                _current_step = 2
            elif "2FA" in text or "المصادقة" in text or "الثنائية" in text:
                _current_step = 3
            elif "الجلسة المحفوظة" in text:
                _current_step = 3
            elif "تم تسجيل الدخول" in text or "login succeeded" in text.lower():
                _current_step = 4
            elif "SheerID" in text or "التحقق" in text:
                if "إنشاء" in text or "create" in text.lower():
                    _current_step = 4
                elif "student" in text.lower() or "بيانات" in text:
                    _current_step = 5
                elif "upload" in text.lower() or "مستند" in text:
                    _current_step = 6
                elif "offer" in text.lower() or "عرض" in text:
                    _current_step = 7
                elif "claim" in text.lower() or "مطالبة" in text:
                    _current_step = 7
                elif "payment" in text.lower() or "دفع" in text:
                    _current_step = 8
                else:
                    _current_step = max(_current_step, 5)
            elif "نجاح" in text or "success" in text.lower() or "🎉" in text:
                _current_step = 9
            elif "فشل" in text or "error" in text.lower() or "❌" in text:
                pass  # keep current step

            elapsed = time.time() - start_time
            error_text = ""
            if "فشل" in text or "خطأ" in text or "error" in text.lower():
                error_text = text.replace("*", "").strip()[:100]

            display = _build_pixel_progress(gmail, _current_step, elapsed, error=error_text)
            await progress_msg.edit_text(display)
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
        log.exception("Pixel auto crashed ver_id=%s", ver_id)
        await models.log_verification_finish(ver_id, user.id, success=False, error=str(exc))
        await models.add_credits(user.id, 1)
        elapsed = time.time() - start_time
        await progress_msg.edit_text(
            _build_pixel_progress(gmail, _current_step, elapsed, error=f"خطأ: {exc}"),
        )
        return

    elapsed = time.time() - start_time

    if result.get("success"):
        await models.log_verification_finish(ver_id, user.id, success=True)
        row = await models.get_user(user.id)
        balance = row["credits"] if row else "—"
        final_text = _build_pixel_progress(gmail, 10, elapsed, success=True)
        final_text += f"\n💰 Balance: {balance} credits"
        await progress_msg.edit_text(final_text, reply_markup=main_menu())
    else:
        await models.log_verification_finish(ver_id, user.id, success=False, error=result.get("error"))
        await models.add_credits(user.id, 1)
        error_msg = result.get("error", "خطأ غير معروف")[:100]
        await progress_msg.edit_text(
            _build_pixel_progress(gmail, _current_step, elapsed, error=error_msg),
            reply_markup=main_menu(),
        )

    # Notify admins
    extra_lines = ""
    if not result.get("success") and result.get("error"):
        extra_lines += f"السبب: {result['error']}\n"
    admin_text = (
        "📥 طلب تحقق جديد (Pixel)\n\n"
        f"المستخدم: {user.id}\n"
        f"اليوزر: @{user.username or '-'}\n"
        f"الخدمة: {meta['label']}\n"
        f"رقم الطلب: {ver_id}\n"
        f"النتيجة: {'نجاح ✅' if result.get('success') else 'فشل ❌'}\n"
        f"الوقت: {int(elapsed)}s\n"
        f"{extra_lines}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id, admin_text)
        except Exception as e:
            log.warning("Failed to notify admin %s: %s", admin_id, e)


# ────────────── Inline button handler ──────────────

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""

    if data.startswith("adm:"):
        from bot.handlers.admin import on_admin_button
        if await on_admin_button(update, ctx):
            return
        await query.answer()
        return

    await query.answer()

    if data == "back":
        _clear_gemini_state(ctx)
        ctx.user_data.pop("pending_service", None)
        row = await models.get_user(query.from_user.id) or {"credits": 0}
        await query.edit_message_text(
            WELCOME_TEXT.format(credits=row.get("credits", 0)),
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return

    if data == "help":
        await query.edit_message_text(HELP_TEXT, parse_mode="Markdown", reply_markup=back_menu())
        return

    if data == "me":
        row = await models.get_user(query.from_user.id)
        if not row:
            row = await models.upsert_user(
                query.from_user.id, query.from_user.username, query.from_user.first_name
            )
        text = (
            "👤 *حسابي*\n\n"
            f"• المعرّف: `{row.get('user_id')}`\n"
            f"• الرصيد: *{row.get('credits', 0)}*\n"
            f"• الناجحة / الإجمالي: "
            f"{row.get('successful_verifications', 0)} / {row.get('total_verifications', 0)}\n"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_menu())
        return

    if data == "ref":
        me = await ctx.bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{query.from_user.id}"
        await query.edit_message_text(
            f"🎁 *رابط الدعوة*\n\nشارك:\n`{link}`\n\n"
            f"كل صديق يبدأ البوت = *+{config.REFERRAL_BONUS} رصيد*",
            parse_mode="Markdown",
            reply_markup=back_menu(),
        )
        return

    if data == "checkin":
        uid = query.from_user.id
        if await models.is_banned(uid):
            await query.edit_message_text("🚫 حسابك محظور.", reply_markup=back_menu())
            return
        if await models.checkin(uid):
            row = await models.get_user(uid)
            await query.edit_message_text(
                f"✅ تم تسجيل الحضور!\n+{config.CHECKIN_REWARD} رصيد\nرصيدك: {row['credits']}",
                reply_markup=back_menu(),
            )
        else:
            await query.edit_message_text("❌ سجّلت حضورك اليوم مسبقاً!", reply_markup=back_menu())
        return

    if data == "usekey":
        await query.edit_message_text(
            "🔑 أرسل الأمر:\n`/use <كود التفعيل>`",
            parse_mode="Markdown",
            reply_markup=back_menu(),
        )
        return

    if data.startswith("svc:"):
        key = data.split(":", 1)[1]
        meta = SERVICE_REGISTRY.get(key)
        if not meta:
            await query.edit_message_text("❌ خدمة غير معروفة.", reply_markup=back_menu())
            return

        if key == "google_one":
            user = query.from_user
            if await models.is_banned(user.id):
                await query.edit_message_text("🚫 حسابك محظور.", reply_markup=back_menu())
                return
            row = await models.get_user(user.id)
            if not row:
                row = await models.upsert_user(user.id, user.username, user.first_name)
            if row["credits"] <= 0:
                await query.edit_message_text(
                    "⚠️ رصيدك منتهي! ادعُ أصدقاء عبر /ref.",
                    reply_markup=back_menu(),
                )
                return
            _clear_gemini_state(ctx)
            ctx.user_data.pop("pending_service", None)
            # Must use KeyboardButton (reply keyboard) for sendData to work
            webapp_kb = ReplyKeyboardMarkup(
                [[KeyboardButton(
                    "⚡ فتح نموذج التفعيل",
                    web_app=WebAppInfo(url=config.WEBAPP_URL),
                )]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await query.edit_message_text(
                "🤖 *Google One / Gemini Pro — تفعيل تلقائي*\n\n"
                "اضغط الزر أدناه لإدخال بيانات حساب Google:",
                parse_mode="Markdown",
            )
            await query.message.reply_text(
                "👇 اضغط الزر:",
                reply_markup=webapp_kb,
            )
            return

        _clear_gemini_state(ctx)
        ctx.user_data["pending_service"] = key
        await query.edit_message_text(
            f"✅ اخترت: *{meta['label']}*\n\n"
            f"_{meta['description']}_\n\n"
            "📨 الآن أرسل الرابط برسالة عادية.",
            parse_mode="Markdown",
            reply_markup=back_menu(),
        )
