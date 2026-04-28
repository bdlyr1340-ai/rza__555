# Merged SheerID Telegram Bot

بوت تلجرام موحّد للتحقق التلقائي عبر SheerID — يعمل على قاعدة بيانات PostgreSQL (Railway).

## الخدمات المدعومة

| الخدمة | الأمر | الوصف |
|--------|-------|-------|
| Google One / Gemini Pro | `/verify` أو الأزرار | تحقق طلابي + تلقائي |
| ChatGPT K12 | `/verify2` أو الأزرار | تحقق للمعلمين |
| Spotify Student | `/verify3` أو الأزرار | اشتراك طلابي |
| Bolt.new Teacher | `/verify4` أو الأزرار | كود تفعيل للمعلمين |
| YouTube Student | `/verify5` أو الأزرار | يوتيوب بريميوم طلابي |
| Perplexity Student | الأزرار | اشتراك طلابي |
| Veterans / Military | الأزرار | تحقق عسكري |

## أوامر المستخدم

- `/start` — القائمة الرئيسية
- `/ping` — فحص البوت
- `/me` — حسابي
- `/ref` — رابط دعوة
- `/qd` — تسجيل حضور يومي (+1 رصيد)
- `/use <كود>` — استخدام كود تفعيل
- `/help` — المساعدة
- `/getV4Code <id>` — استعلام كود Bolt.new

## أوامر الأدمن

- `/admin` — لوحة التحكم
- `/stats` — إحصائيات
- `/addcredit <user_id> <amount>` — إضافة رصيد
- `/ban` / `/unban` — حظر / رفع حظر
- `/blacklist` — قائمة المحظورين
- `/broadcast <رسالة>` — بث رسالة
- `/genkey <كود> <رصيد> [عدد] [أيام]` — إنشاء كود تفعيل
- `/listkeys` — عرض الأكواد
- `/addcard` — إضافة بطاقة ائتمان
- `/cards` — عرض البطاقات
- `/delcard <id>` — حذف بطاقة

## النشر على Railway

1. أنشئ مشروع جديد على Railway
2. أضف قاعدة بيانات PostgreSQL
3. اربط الريبو من GitHub
4. أضف متغيرات البيئة:
   - `BOT_TOKEN`
   - `DATABASE_URL` (يتم تعبئته تلقائياً من Railway)
   - `ADMIN_IDS` (أرقام المشرفين مفصولة بفاصلة)

## التشغيل المحلي

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# عدّل .env بالقيم الصحيحة
python -m bot.main
```

## Docker

```bash
docker build -t merged-tgbot .
docker run --env-file .env merged-tgbot
```
