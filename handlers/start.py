"""أمر /start والقائمة الرئيسية."""
from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.db import models
from bot.services import SERVICE_REGISTRY
from bot.utils.keyboards import main_menu, back_menu

log = logging.getLogger(__name__)


WELCOME_TEXT = (
    "👋 *مرحباً بك في بوت SheerID*\n\n"
    "بوت تحقق آلي يدعم 7 خدمات (Spotify, YouTube, Gemini, Bolt, ChatGPT K12, Veterans, Perplexity).\n\n"
    "📌 *كيف أستخدمه؟*\n"
    "1. اضغط زر الخدمة المطلوبة من الأسفل\n"
    "2. أرسل رابط SheerID (يبدأ بـ `https://services.sheerid.com/...`)\n"
    "3. سينتهي البوت من التحقق خلال دقيقة تقريباً ✅\n\n"
    "💎 *رصيدك الحالي:* `{credits}`\n"
    "كل عملية تحقق تخصم نقطة واحدة.\n"
    "يمكنك زيادة رصيدك عن طريق دعوة أصدقائك 🎁"
)

HELP_TEXT = (
    "📖 *دليل الاستخدام*\n\n"
    "• تحصل على *3 عمليات مجانية* عند التسجيل.\n"
    "• كل دعوة صديق ناجحة = *+5 رصيد*.\n"
    "• تستطيع إرسال رابط SheerID مباشرة دون اختيار الخدمة، والبوت سيكشفها تلقائياً.\n\n"
    "*الأوامر المتاحة:*\n"
    "/start — القائمة الرئيسية\n"
    "/me — عرض حسابي ورصيدي\n"
    "/ref — رابط الدعوة الخاص بك\n"
    "/help — هذه الرسالة"
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
        await update.message.reply_text("🚫 حسابك محظور من استخدام البوت.")
        return

    await update.message.reply_markdown(
        WELCOME_TEXT.format(credits=row["credits"]),
        reply_markup=main_menu(),
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_markdown(HELP_TEXT, reply_markup=back_menu())


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
        f"• إجمالي العمليات: {row['total_verifications']}\n"
        f"• الناجحة: {row['successful_verifications']}\n"
    )
    await update.message.reply_markdown(text, reply_markup=back_menu())


async def cmd_ref(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    me = await ctx.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{user.id}"
    text = (
        "🎁 *دعوة الأصدقاء*\n\n"
        f"شارك هذا الرابط، وكل صديق يبدأ البوت عبره يمنحك *+{config.REFERRAL_BONUS} رصيد*:\n\n"
        f"`{link}`"
    )
    await update.message.reply_markdown(text, reply_markup=back_menu())


# ============ Callback queries من الأزرار ============

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "back":
        row = await models.get_user(query.from_user.id) or {}
        await query.edit_message_text(
            WELCOME_TEXT.format(credits=row.get("credits", 0)),
            parse_mode="Markdown", reply_markup=main_menu(),
        )
        return

    if data == "help":
        await query.edit_message_text(HELP_TEXT, parse_mode="Markdown", reply_markup=back_menu())
        return

    if data == "me":
        row = await models.get_user(query.from_user.id) or {}
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
            parse_mode="Markdown", reply_markup=back_menu(),
        )
        return

    if data.startswith("svc:"):
        key = data.split(":", 1)[1]
        meta = SERVICE_REGISTRY.get(key)
        if not meta:
            await query.edit_message_text("❌ خدمة غير معروفة.", reply_markup=back_menu())
            return
        ctx.user_data["pending_service"] = key
        await query.edit_message_text(
            f"✅ اخترت: *{meta['label']}*\n\n"
            f"_{meta['description']}_\n\n"
            "📨 الآن أرسل رابط SheerID الخاص بك في رسالة عادية.",
            parse_mode="Markdown",
            reply_markup=back_menu(),
        )
