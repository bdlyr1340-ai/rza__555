import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import TOKEN, FRIDA_AGENTS
from database import db
from frida_client import run_frida_script

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        f"مرحباً {user.first_name}!\n"
        "البوت جاهز.\n"
        "للتشغيل: /run_frida <device_id>\n"
        "عرض الأجهزة المتاحة: /devices"
    )

async def list_devices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not FRIDA_AGENTS:
        await update.message.reply_text("لا توجد أجهزة مسجلة حالياً.")
        return
    devices = "\n".join([f"- {d}" for d in FRIDA_AGENTS.keys()])
    await update.message.reply_text(f"الأجهزة المتاحة:\n{devices}")

async def run_frida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("الاستخدام: /run_frida <device_id>\nمثال: /run_frida myphone")
        return
    device = context.args[0].strip()
    user_id = update.effective_user.id

    await update.message.reply_text(f"⏳ جاري تشغيل السكريبت على الجهاز '{device}' ...")
    result = await run_frida_script(device, user_id)
    status = "success" if result.startswith("✅") else "failed"
    await db.log_frida_run(user_id, device, status, result)
    await update.message.reply_text(result)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("devices", list_devices))
    app.add_handler(CommandHandler("run_frida", run_frida))
    app.run_polling()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(db.connect())
    main()