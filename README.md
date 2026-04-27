# RZA Telegram Bot - Railway Ready

نسخة مرتبة لريلوي مع هيكل ملفات كامل وأزرار عربية.

## Railway variables

```env
BOT_TOKEN=
DATABASE_URL=
ADMIN_IDS=
DEFAULT_CREDITS=3
REFERRAL_BONUS=5
LOG_LEVEL=INFO
```

## Start Command

```bash
python main.py
```

## Test

بعد النشر أرسل للبوت:

```text
/ping
/start
```

## ملاحظات

- تم ترتيب الملفات داخل مجلد `bot` حتى لا يصير تعارض باسم `db`.
- تم إصلاح تشغيل Railway على Python.
- تم إضافة `delete_webhook` حتى يشتغل Polling مباشرة.
- الأزرار صارت عربية.
- الروابط تُسجل في قاعدة البيانات وتصل إشعارات للأدمن إذا `ADMIN_IDS` مضبوط.
