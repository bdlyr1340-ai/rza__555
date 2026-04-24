# مساعد الدفع - Telegram Bot

بوت تلگرام احترافي مرتبط بموقع مساعد الدفع بشكل آمن عبر WebApp.

## Railway Variables

```env
BOT_TOKEN=توكن_البوت
ADMIN_IDS=ايديك
DATABASE_URL=${{Postgres.DATABASE_URL}}
PORT=3000
SITE_URL=https://gpt.aide.freespaces.app/
SUPPORT_URL=https://t.me/t4i44s
NODE_ENV=production
```

## تشغيل محلي

```bash
npm install
cp .env.example .env
npm start
```

## أوامر الأدمن

```text
/admin
/orders
/order 1
/approve 1
/reject 1 السبب
/broadcast نص الرسالة
```

## التعديل
كل النصوص، الأزرار، أنواع الاشتراك، العملات، وطرق الدفع داخل `index.js`.
