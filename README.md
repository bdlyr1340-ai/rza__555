# مساعد الدفع Telegram Bot

بوت تلگرام يعمل مثل فكرة موقع مساعد الدفع:

1. المستخدم يضغط **إرسال السيشن**.
2. يرسل السيشن برسالة واحدة.
3. البوت يعرض طرق الدفع.
4. المستخدم يختار طريقة الدفع.
5. البوت يرسل تفاصيل الدفع.
6. المستخدم يرسل رمز التحويل ورمز الملاحظة / Memo.
7. الطلب يصل للأدمن ويقدر يقبله أو يرفضه.

## أهم ملف للتعديل

عدّل فقط ملف:

```bash
index.js
```

من أعلى الملف داخل `APP_CONFIG` تقدر تعدل:

- اسم البوت
- نصوص العربي والإنكليزي
- طرق الدفع
- رابط الموقع
- رابط الدعم

## Railway Variables

استخدم هذه المتغيرات:

```env
BOT_TOKEN=PUT_YOUR_BOT_TOKEN
ADMIN_IDS=PUT_YOUR_TELEGRAM_ID
DATABASE_URL=${{Postgres.DATABASE_URL}}
PORT=3000
SITE_URL=https://gpt.aide.freespaces.app/
SUPPORT_URL=https://t.me/t4i44s
NODE_ENV=production
RAILWAY_VOLUME_MOUNT_PATH=/data
```

إذا تستخدم `ADMIN_ID` بدل `ADMIN_IDS`، الكود يدعم الاثنين، لكن الأفضل `ADMIN_IDS`.

## أوامر الأدمن

```text
/admin
/orders
/approve ORDER_ID
/reject ORDER_ID
/broadcast نص الرسالة
```

## التشغيل المحلي

```bash
npm install
cp .env.example .env
npm run dev
```

## النشر

ارفع الملفات على GitHub، ثم اربط GitHub مع Railway، وأضف PostgreSQL، ثم أضف المتغيرات.
