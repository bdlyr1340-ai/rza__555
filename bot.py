import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TOKEN, FRIDA_AGENTS
from database import db
from frida_client import run_frida_script

logging.basicConfig(level=logging.INFO)

# قائمة الأجهزة (للاستخدام السريع)
def get_devices_list():
    return list(FRIDA_AGENTS.keys())

# لوحة التحكم الرئيسية
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📱 عرض الأجهزة", callback_data="show_devices")],
        [InlineKeyboardButton("🚀 تشغيل Frida على جهاز", callback_data="run_frida_menu")],
        [InlineKeyboardButton("📊 عدد المستخدمين", callback_data="users_count")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("🔧 لوحة تحكم البوت:", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text("🔧 لوحة تحكم البوت:", reply_markup=reply_markup)

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_user(user.id, user.username, user.first_name)
    await main_menu(update, context)

# عرض الأجهزة كأزرار
async def show_devices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    devices = get_devices_list()
    if not devices:
        await query.edit_message_text("❌ لا توجد أجهزة مسجلة.")
        return
    keyboard = [[InlineKeyboardButton(f"📱 {d}", callback_data=f"select_device_{d}")] for d in devices]
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    await query.edit_message_text("اختر جهازاً:", reply_markup=InlineKeyboardMarkup(keyboard))

# عرض قائمة أجهزة للتشغيل
async def run_frida_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    devices = get_devices_list()
    if not devices:
        await query.edit_message_text("❌ لا توجد أجهزة. أضفها في متغير FRIDA_AGENTS.")
        return
    keyboard = [[InlineKeyboardButton(f"▶️ {d}", callback_data=f"run_frida_{d}")] for d in devices]
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    await query.edit_message_text("اختر جهازاً لتشغيل السكريبت:", reply_markup=InlineKeyboardMarkup(keyboard))

# تشغيل Frida على جهاز محدد
async def run_frida_on_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    device = query.data.split("_")[-1]  # استخراج اسم الجهاز
    user_id = query.from_user.id

    await query.edit_message_text(f"⏳ جاري تشغيل السكريبت على الجهاز `{device}` ...", parse_mode="Markdown")
    result = await run_frida_script(device, user_id)
    status = "success" if result.startswith("✅") else "failed"
    await db.log_frida_run(user_id, device, status, result)
    # إظهار النتيجة وزر رجوع
    keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]]
    await query.message.reply_text(result, reply_markup=InlineKeyboardMarkup(keyboard))

# عدد المستخدمين
async def users_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    async with db.pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
    await query.edit_message_text(f"👥 إجمالي المستخدمين: {count}", reply_markup=InlineKeyboardMarkup(keyboard))

# معالج ضغطات الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "main_menu":
        await main_menu(update, context)
    elif data == "show_devices":
        await show_devices(update, context)
    elif data == "run_frida_menu":
        await run_frida_menu(update, context)
    elif data == "users_count":
        await users_count(update, context)
    elif data.startswith("select_device_"):
        device = data.replace("select_device_", "")
        # عرض معلومات الجهاز (يمكن توسيعها)
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        await query.edit_message_text(f"الجهاز: {device}\nعنوانه: {FRIDA_AGENTS.get(device)}", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("run_frida_"):
        await run_frida_on_device(update, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(db.connect())
    main()