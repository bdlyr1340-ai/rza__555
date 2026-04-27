from __future__ import annotations

import asyncio
import logging
import signal
from typing import Optional

from aiohttp import web
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import rza_database as database

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("rza-telegram-bot")


def is_admin(user_id: Optional[int]) -> bool:
    return bool(user_id and user_id in config.ADMIN_IDS)


def main_keyboard(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("👤 حسابي", callback_data="account"),
            InlineKeyboardButton("🎁 رابط الدعوة", callback_data="invite"),
        ],
        [
            InlineKeyboardButton("🌐 English / العربية", callback_data="language"),
            InlineKeyboardButton("ℹ️ المساعدة", callback_data="help"),
        ],
    ]
    if is_admin(user_id):
        rows.append([InlineKeyboardButton("⚙️ لوحة الأدمن", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("العربية 🇮🇶", callback_data="lang_ar"),
                InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"),
            ],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="home")],
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="home")]])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="home")],
        ]
    )


async def ensure_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return None

    referred_by = None
    if context.args:
        arg = context.args[0].strip()
        if arg.startswith("ref_") and arg[4:].isdigit():
            referred_by = int(arg[4:])

    row = await database.upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        referred_by=referred_by,
    )
    return row


async def send_home(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    row = await ensure_user(update, context)
    user = update.effective_user
    if not user or not row:
        return
    if row.get("is_banned"):
        text = "🚫 حسابك محظور من استخدام البوت."
        if update.callback_query and edit:
            await update.callback_query.edit_message_text(text)
        else:
            await update.effective_message.reply_text(text)
        return

    lang = row.get("language", "ar")
    if lang == "en":
        text = (
            "Hello! The bot is running successfully ✅\n\n"
            f"Your credits: {row['credits']}\n"
            "Use the buttons below."
        )
    else:
        text = (
            "هلا بيك حبيبي 🌟\n\n"
            "البوت اشتغل بنجاح على Railway ✅\n"
            f"رصيدك الحالي: {row['credits']}\n\n"
            "استخدم الأزرار بالأسفل."
        )

    if update.callback_query and edit:
        await update.callback_query.edit_message_text(text, reply_markup=main_keyboard(user.id))
    else:
        await update.effective_message.reply_text(text, reply_markup=main_keyboard(user.id))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_home(update, context)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    text = (
        "الأوامر المتوفرة:\n"
        "/start - تشغيل البوت\n"
        "/help - المساعدة\n"
        "/id - عرض آيديك\n"
        "/account - حسابك\n"
        "/ref - رابط الدعوة\n\n"
        "أوامر الأدمن:\n"
        "/stats\n"
        "/addcredits USER_ID AMOUNT\n"
        "/ban USER_ID\n"
        "/unban USER_ID\n"
        "/broadcast الرسالة"
    )
    await update.effective_message.reply_text(text, reply_markup=back_keyboard())


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        await update.effective_message.reply_text(f"ID: <code>{user.id}</code>", parse_mode=ParseMode.HTML)


async def account_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = await ensure_user(update, context)
    if not row:
        return
    username = row.get("username") or "بدون"
    text = (
        "👤 حسابك\n\n"
        f"ID: <code>{row['user_id']}</code>\n"
        f"Username: @{username}\n"
        f"Credits: <b>{row['credits']}</b>\n"
        f"Language: <b>{row.get('language', 'ar')}</b>\n"
        f"Messages: <b>{row.get('total_messages', 0)}</b>"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard())


async def ref_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    user = update.effective_user
    if not user:
        return
    bot_user = await context.bot.get_me()
    link = f"https://t.me/{bot_user.username}?start=ref_{user.id}"
    await update.effective_message.reply_text(
        "🎁 رابط دعوتك:\n"
        f"<code>{link}</code>\n\n"
        f"كل دعوة ناجحة تضيف لك {config.REFERRAL_BONUS} كريدت.",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard(),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user:
        return
    await query.answer()

    row = await database.upsert_user(query.from_user.id, query.from_user.username, query.from_user.first_name)
    if row.get("is_banned"):
        await query.edit_message_text("🚫 حسابك محظور من استخدام البوت.")
        return

    data = query.data or "home"

    if data == "home":
        await send_home(update, context, edit=True)
        return

    if data == "account":
        username = row.get("username") or "بدون"
        await query.edit_message_text(
            "👤 حسابك\n\n"
            f"ID: <code>{row['user_id']}</code>\n"
            f"Username: @{username}\n"
            f"Credits: <b>{row['credits']}</b>\n"
            f"Language: <b>{row.get('language', 'ar')}</b>\n"
            f"Messages: <b>{row.get('total_messages', 0)}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(),
        )
        return

    if data == "invite":
        bot_user = await context.bot.get_me()
        link = f"https://t.me/{bot_user.username}?start=ref_{query.from_user.id}"
        await query.edit_message_text(
            "🎁 رابط دعوتك:\n"
            f"<code>{link}</code>\n\n"
            f"كل دعوة ناجحة تضيف لك {config.REFERRAL_BONUS} كريدت.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(),
        )
        return

    if data == "language":
        await query.edit_message_text("اختار اللغة / Choose language:", reply_markup=language_keyboard())
        return

    if data in {"lang_ar", "lang_en"}:
        lang = "ar" if data == "lang_ar" else "en"
        await database.set_language(query.from_user.id, lang)
        msg = "تم تغيير اللغة للعربية ✅" if lang == "ar" else "Language changed to English ✅"
        await query.edit_message_text(msg, reply_markup=main_keyboard(query.from_user.id))
        return

    if data == "help":
        await query.edit_message_text(
            "ℹ️ المساعدة\n\n"
            "استخدم الأزرار لإدارة حسابك، عرض الكريدت، ورابط الدعوة.\n"
            "Use the buttons to manage your account and invite link.",
            reply_markup=back_keyboard(),
        )
        return

    if data == "admin":
        if not is_admin(query.from_user.id):
            await query.edit_message_text("ما عندك صلاحية.", reply_markup=back_keyboard())
            return
        await query.edit_message_text("⚙️ لوحة الأدمن", reply_markup=admin_keyboard())
        return

    if data == "admin_stats":
        if not is_admin(query.from_user.id):
            await query.edit_message_text("ما عندك صلاحية.", reply_markup=back_keyboard())
            return
        s = await database.stats()
        await query.edit_message_text(
            "📊 الإحصائيات\n\n"
            f"المستخدمين: <b>{s['users']}</b>\n"
            f"اليوم: <b>{s['today']}</b>\n"
            f"المحظورين: <b>{s['banned']}</b>\n"
            f"الإحالات: <b>{s['referrals']}</b>\n"
            f"الرسائل: <b>{s['messages']}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_keyboard(),
        )
        return


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id if user else None):
        await update.effective_message.reply_text("ما عندك صلاحية.")
        return
    s = await database.stats()
    await update.effective_message.reply_text(
        "📊 الإحصائيات\n\n"
        f"المستخدمين: {s['users']}\n"
        f"اليوم: {s['today']}\n"
        f"المحظورين: {s['banned']}\n"
        f"الإحالات: {s['referrals']}\n"
        f"الرسائل: {s['messages']}"
    )


async def addcredits_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id if user else None):
        await update.effective_message.reply_text("ما عندك صلاحية.")
        return
    if len(context.args) != 2 or not context.args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text("الاستخدام: /addcredits USER_ID AMOUNT")
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("المبلغ لازم يكون رقم.")
        return
    new_balance = await database.add_credits(target_id, amount)
    if new_balance is None:
        await update.effective_message.reply_text("المستخدم غير موجود.")
    else:
        await update.effective_message.reply_text(f"تم ✅ الرصيد الجديد: {new_balance}")


async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id if user else None):
        await update.effective_message.reply_text("ما عندك صلاحية.")
        return
    if len(context.args) != 1 or not context.args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text("الاستخدام: /ban USER_ID")
        return
    await database.set_banned(int(context.args[0]), True)
    await update.effective_message.reply_text("تم الحظر ✅")


async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id if user else None):
        await update.effective_message.reply_text("ما عندك صلاحية.")
        return
    if len(context.args) != 1 or not context.args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text("الاستخدام: /unban USER_ID")
        return
    await database.set_banned(int(context.args[0]), False)
    await update.effective_message.reply_text("تم إلغاء الحظر ✅")


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id if user else None):
        await update.effective_message.reply_text("ما عندك صلاحية.")
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("الاستخدام: /broadcast رسالتك")
        return
    ids = await database.all_active_user_ids()
    sent = 0
    failed = 0
    await update.effective_message.reply_text(f"جاري الإرسال إلى {len(ids)} مستخدم…")
    for uid in ids:
        try:
            await context.bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.04)
        except TelegramError:
            failed += 1
    await update.effective_message.reply_text(f"تم الإرسال ✅\nنجح: {sent}\nفشل: {failed}")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = await ensure_user(update, context)
    user = update.effective_user
    if not user or not row:
        return
    if row.get("is_banned"):
        await update.effective_message.reply_text("🚫 حسابك محظور.")
        return
    await database.touch_message(user.id)
    await update.effective_message.reply_text(
        "وصلت رسالتك ✅\nاختار من الأزرار أو استخدم /help",
        reply_markup=main_keyboard(user.id),
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Telegram update error", exc_info=context.error)


async def health(_: web.Request) -> web.Response:
    return web.Response(text="Bot is running ✅")


async def start_web_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    log.info("Health server started on port %s", config.PORT)
    return runner


def setup_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("id", id_cmd))
    application.add_handler(CommandHandler("account", account_cmd))
    application.add_handler(CommandHandler("me", account_cmd))
    application.add_handler(CommandHandler("ref", ref_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("addcredits", addcredits_cmd))
    application.add_handler(CommandHandler("addcredit", addcredits_cmd))
    application.add_handler(CommandHandler("ban", ban_cmd))
    application.add_handler(CommandHandler("unban", unban_cmd))
    application.add_handler(CommandHandler("broadcast", broadcast_cmd))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_error_handler(error_handler)


async def run() -> None:
    config.validate()
    await database.connect_db()
    runner = await start_web_server()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    application = Application.builder().token(config.BOT_TOKEN).build()
    setup_handlers(application)

    await application.initialize()
    await application.start()
    if application.updater is None:
        raise RuntimeError("Telegram updater was not created")
    await application.updater.start_polling(drop_pending_updates=True)
    log.info("Telegram bot started")

    try:
        await stop_event.wait()
    finally:
        log.info("Stopping bot...")
        if application.updater is not None:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await runner.cleanup()
        await database.close_db()


if __name__ == "__main__":
    asyncio.run(run())
