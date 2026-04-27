"""نقطة تشغيل البوت — long polling."""
from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters,
)

from bot import config
from bot.db.connection import init_pool, close_pool
from bot.handlers import start as h_start, verify as h_verify, admin as h_admin


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def _post_init(app: Application) -> None:
    await init_pool()
    me = await app.bot.get_me()
    logging.info("🤖 البوت يعمل: @%s", me.username)


async def _post_shutdown(app: Application) -> None:
    await close_pool()


def build_app() -> Application:
    config.validate()

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    # أوامر المستخدم
    app.add_handler(CommandHandler("start", h_start.cmd_start))
    app.add_handler(CommandHandler("help",  h_start.cmd_help))
    app.add_handler(CommandHandler("me",    h_start.cmd_me))
    app.add_handler(CommandHandler("ref",   h_start.cmd_ref))

    # أوامر الأدمن
    app.add_handler(CommandHandler("admin",     h_admin.cmd_admin))
    app.add_handler(CommandHandler("stats",     h_admin.cmd_stats))
    app.add_handler(CommandHandler("addcredit", h_admin.cmd_addcredit))
    app.add_handler(CommandHandler("ban",       h_admin.cmd_ban))
    app.add_handler(CommandHandler("unban",     h_admin.cmd_unban))
    app.add_handler(CommandHandler("broadcast", h_admin.cmd_broadcast))

    # أزرار
    app.add_handler(CallbackQueryHandler(h_start.on_button))

    # رسائل النص العادية (روابط SheerID)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h_verify.on_text))

    return app


def main() -> None:
    _setup_logging()
    app = build_app()
    logging.info("🚀 بدء polling…")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
