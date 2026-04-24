import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TOKEN, FRIDA_AGENTS
from database import db
from frida_client import run_frida_script

logging.basicConfig(level=logging.INFO)

# الأزرار الرئيسية
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📱 عرض الأجهزة", callback_data="show_devices")],
        [InlineKeyboardButton("🚀 تشغيل Frida", callback_data="run_frida_menu")],
        [InlineKeyboardButton("📊 عدد المستخدمين", callback_data="users_count")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]])

# قائمة الأجهزة
def get_devices():
    return list(FRIDA_AGENTS.keys())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_user(user.id, user.username, user.first_name)
    await update.message.reply_text("🔧 لوحة تحكم البوت:", reply_markup=main_keyboard())

async def show_devices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    devices = get_devices()
    if not devices:
        await query.edit_message_text("❌ لا توجد أجهزة.", reply_markup=back_button())
        return
    keyboard = [[InlineKeyboardButton(f"📱 {d}", callback_data=f"select_{d}")] for d in devices]
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    await query.edit_message_text("📱 الأجهزة:", reply_markup=InlineKeyboardMarkup(keyboard))

async def run_frida_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    devices = get_devices()
    if not devices:
        await query.edit_message_text("❌ لا توجد أجهزة.", reply_markup=back_button())
        return
    keyboard = [[InlineKeyboardButton(f"▶️ {d}", callback_data=f"run_{d}")] for d in devices]
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    await query.edit_message_text("اختر جهازاً:", reply_markup=InlineKeyboardMarkup(keyboard))

async def users_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    async with db.pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
    await query.edit_message_text(f"👥 المستخدمون: {count}", reply_markup=back_button())

async def run_frida_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    device = query.data.split("_")[1]
    user_id = query.from_user.id
    await query.edit_message_text(f"⏳ جاري التشغيل على {device}...")
    result = await run_frida_script(device, user_id)
    status = "success" if result.startswith("✅") else "failed"
    await db.log_frida_run(user_id, device, status, result)
    # إرسال النتيجة مع زر رجوع
    await query.message.reply_text(result, reply_markup=back_button())

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔧 لوحة التحكم:", reply_markup=main_keyboard())

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "main_menu":
        await main_menu(update, context)
    elif data == "show_devices":
        await show_devices(update, context)
    elif data == "run_frida_menu":
        await run_frida_menu(update, context)
    elif data == "users_count":
        await users_count(update, context)
    elif data.startswith("select_"):
        device = data.split("_")[1]
        url = FRIDA_AGENTS.get(device, "غير معروف")
        await update.callback_query.edit_message_text(f"جهاز: {device}\nالعنوان: {url}", reply_markup=back_button())
    elif data.startswith("run_"):
        await run_frida_device(update, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.run_polling()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(db.connect())
    main()
