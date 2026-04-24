# مساعد الدفع - Telegram Bot

بوت تلگرام احترافي مرتبط بموقع مساعد الدفع.

## المتغيرات في Railway

```env
BOT_TOKEN=توكن_البوت
ADMIN_IDS=1694736891
DATABASE_URL=${{Postgres.DATABASE_URL}}
PORT=3000
SITE_URL=https://gpt.aide.freespaces.app/
API_BASE=https://gpt.serve.freespaces.app
SUPPORT_URL=https://t.me/t4i44s
NODE_ENV=production
```

## التشغيل

```bash
npm install
npm start
```

## ملاحظات

- كل التعديل الأساسي من ملف `index.js`.
- البوت يستخدم API الموقع المكتشف:
  - `POST /api/user/login`
  - `GET /api/user/info`
  - `POST /api/user/logout`
  - `POST /api/user/free/register`
- أزرار الدفع وتجديد الاشتراك تحتوي محاولات تلقائية لأكثر من endpoint، وإذا تغير مسار الموقع تعدله من أعلى `index.js` في قسم `SITE_ENDPOINTS` فقط.
