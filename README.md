# Railway Telegram Bot - Fixed Buttons

## Variables المطلوبة في Railway

BOT_TOKEN=توكن_البوت_من_BotFather
DATABASE_URL=ينضاف تلقائياً بعد ربط PostgreSQL
FRIDA_AGENTS={"myphone":"http://IP:5000"}

## التشغيل

Railway سيشغل:

npm install
npm start

## سبب المشكلة القديمة

ملف index.js كان يحتوي كود Python، بينما package.json يشغل Node.js:

node index.js

لذلك الأزرار لا تظهر أو البوت يتوقف.
