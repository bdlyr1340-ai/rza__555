"""أمر /start والقائمة الرئيسية."""
from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.db import models
from bot.services import SERVICE_REGISTRY
from bot.services.sheerid import verify_gemini_auto
from bot.utils.keyboards import back_menu, main_menu

log = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 *أهلاً بيك بالبوت*\n\n"
    "اختر الخدمة المطلوبة من الأزرار بالأسفل.\n"
    "وتگدر ترسل الرابط بعد اختيار الخدمة حتى ينحفظ طلبك بقاعدة البيانات.\n\n"
    "💎 *رصيدك الحالي:* `{credits}`\n"
)

HELP_TEXT = (
    "📖 *دليل الاستخدام*\n\n"
    "• اضغط على الخدمة من الأزرار.\n"
    "• أرسل الرابط بعدها برسالة عادية.\n"
    "• البوت يحفظ الطلب ويربطه بحسابك وقاعدة البيانات.\n\n"
    "*الأوامر:*\n"
    "/start — القائمة الرئيسية\n"
    "/ping — فحص استجابة البوت\n"
    "/me — حسابي ورصيدي\n"
    "/ref — رابط الدعوة\n"
    "/help — المساعدة"
)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = ctx.args or []

    referred_by = None
    if args and args[0].startswith("ref_") and args[0][4:].isdigit():
        referred_by = int(args[0][4:])

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
    await update.effective_message.reply_markdown(HELP_TEXT, reply_markup=back_menu())


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


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "back":
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
            row = await models.upsert_user(query.from_user.id, query.from_user.username, query.from_user.first_name)
        text = (
            "👤 *حسابي*\n\n"
            f"• المعرّف: `{row.get('user_id')}`\n"
            f"• الرصيد: *{row.get('credits', 0)}*\n"
            f"• الناجحة / الإجمالي: {row.get('successful_verifications', 0)} / {row.get('total_verifications', 0)}\n"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_menu())
        return

    if data == "ref":
        me = await ctx.bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{query.from_user.id}"
        await query.edit_message_text(
            f"🎁 *رابط الدعوة*\n\nشارك:\n`{link}`\n\nكل صديق يبدأ البوت = *+{config.REFERRAL_BONUS} رصيد*",
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

        # Auto-verify for Google One / Gemini — start conversation to collect credentials
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
                    "⚠️ رصيدك منتهي! ادعُ أصدقاء عبر /ref حتى تحصل على رصيد إضافي.",
                    reply_markup=back_menu(),
                )
                return

            # Start conversation — ask for email first
            ctx.user_data["gemini_flow"] = "email"
            await query.edit_message_text(
                "🤖 *جوجل ون / جيمناي — تحقق تلقائي*\n\n"
                "📧 *الخطوة 1/3:* أرسل إيميل Gmail الخاص بك:",
                parse_mode="Markdown",
                reply_markup=back_menu(),
            )
            return

        ctx.user_data["pending_service"] = key
        await query.edit_message_text(
            f"✅ اخترت: *{meta['label']}*\n\n"
            f"_{meta['description']}_\n\n"
            "📨 الآن أرسل الرابط برسالة عادية حتى ينحفظ طلبك.",
            parse_mode="Markdown",
            reply_markup=back_menu(),
        )
