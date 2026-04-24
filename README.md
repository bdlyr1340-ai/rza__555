# Telegram GPT Aide Bot

بوت تلگرام مرتب يدعم العربية والإنكليزية، يفتح الموقع كـ WebApp، ويوفر أزرار وخطوات طلب داخل البوت، مع حفظ المستخدمين والطلبات داخل Railway PostgreSQL.

## الملفات

- `index.js` — الملف الرئيسي. عدّل النصوص، الأزرار، المنتجات، روابط الدعم، وطرق الدفع من هذا الملف.
- `package.json` — مكتبات التشغيل.
- `.env.example` — انسخه إلى `.env` محلياً أو أضف المتغيرات في Railway.
- `railway.json` و `Procfile` — إعداد تشغيل Railway.

## التشغيل المحلي

```bash
npm install
cp .env.example .env
# عدّل BOT_TOKEN و DATABASE_URL داخل .env
npm run dev
```

## النشر على GitHub

```bash
git init
git add .
git commit -m "Initial Telegram bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## النشر على Railway

1. افتح Railway وأنشئ مشروع جديد.
2. اختر Deploy from GitHub repo.
3. أضف خدمة PostgreSQL من Railway.
4. أضف المتغيرات التالية داخل Variables:
   - `BOT_TOKEN`
   - `BOT_USERNAME`
   - `ADMIN_IDS`
   - `SITE_URL=https://gpt.aide.freespaces.app/`
   - `SUPPORT_URL=https://t.me/t4i44s`
   - `PUBLIC_URL=https://your-project.up.railway.app`
   - `NODE_ENV=production`
5. بعد أول تشغيل، افتح رابط:

```text
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<PUBLIC_URL>/telegram
```

مثال:

```text
https://api.telegram.org/bot123456:ABC/setWebhook?url=https://mybot.up.railway.app/telegram
```

## التعديل من index.js فقط

داخل أعلى `index.js` ستجد كائن `APP_CONFIG`، منه تعدّل:

- اسم المشروع.
- رابط الموقع.
- روابط الدعم.
- المنتجات أو الخدمات.
- طرق الدفع.
- نصوص العربية والإنكليزية.
- أزرار القوائم.

## أوامر الأدمن

- `/admin` عرض لوحة الإدارة.
- `/orders` آخر الطلبات.
- `/approve ORDER_ID` قبول طلب.
- `/reject ORDER_ID` رفض طلب.
- `/broadcast نص الرسالة` إرسال رسالة لكل المستخدمين.

## ملاحظة مهمة

الموقع `https://gpt.aide.freespaces.app/` لم يظهر منه API عام واضح، لذلك البوت جاهز كواجهة Telegram منظمة + WebApp + نظام طلبات. إذا عندك API للموقع أو طريقة تسجيل/شراء رسمية، ضع endpoint داخل دوال `siteApi` في `index.js` لتصبح العمليات مرتبطة مباشرة بالموقع.
