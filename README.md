# Telegram Bot + Frida (Node.js)

## النشر على Railway

1. ارفع الملفات إلى GitHub.
2. في Railway: New Project → Deploy from GitHub.
3. أضف المتغيرات:
   - `BOT_TOKEN`
   - `DATABASE_URL` (بعد إضافة PostgreSQL عبر Provision)
   - `FRIDA_AGENTS` = `{"myphone":"http://IP:5000"}`
4. سيتم التشغيل تلقائياً.

## تحديث السكريبت

يمكنك تعديل `hook_1m.js` مباشرة في المستودع، ثم دفع التغييرات إلى GitHub، وسيعيد Railway نشر البوت تلقائياً.