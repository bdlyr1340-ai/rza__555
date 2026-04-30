# 🤖 Merged SheerID Telegram Bot

بوت تلجرام موحّد للتحقق التلقائي عبر SheerID — يعمل على قاعدة بيانات PostgreSQL (Railway).

> 💡 **آخر تحديث:** زيادة مدة انتظار SheerID من 5 دقائق إلى 15 دقيقة (قابلة للتعديل عبر `SHEERID_POLL_MINUTES`).

---

## 📋 الخدمات المدعومة

| الخدمة | الأمر | الوصف |
|--------|-------|-------|
| Google One / Gemini Pro | `/verify` أو `/pixel` (WebApp) | تحقق طلابي + تلقائي |
| ChatGPT K12 | `/verify2` | تحقق للمعلمين |
| Spotify Student | `/verify3` | اشتراك طلابي |
| Bolt.new Teacher | `/verify4` | كود تفعيل للمعلمين |
| YouTube Student | `/verify5` | يوتيوب بريميوم طلابي |
| Perplexity Student | الأزرار | اشتراك طلابي |
| Veterans / Military | الأزرار | تحقق عسكري |

---

## 📂 هيكل المشروع

```
rza__555-main/
├── Dockerfile               # صورة Docker للنشر
├── Procfile                 # ملف تشغيل (Heroku/Railway)
├── railway.json             # إعدادات Railway
├── requirements.txt         # مكتبات Python
├── main.py                  # نقطة البداية
├── .env.example             # نموذج المتغيرات
├── webapp/
│   └── index.html           # واجهة Pixel (WebApp)
└── bot/
    ├── main.py              # تجميع الـ handlers والتشغيل
    ├── config.py            # قراءة المتغيرات من البيئة
    ├── db/
    │   ├── connection.py    # اتصال PostgreSQL
    │   ├── models.py        # عمليات قاعدة البيانات
    │   └── migrations.sql   # هيكل الجداول
    ├── handlers/
    │   ├── start.py         # /start, القائمة، WebApp
    │   ├── verify.py        # أوامر /verify, /verify2..5
    │   └── admin.py         # أوامر الأدمن
    ├── services/
    │   ├── __init__.py      # سجل الخدمات SERVICE_REGISTRY
    │   └── sheerid.py       # محرّك التحقق + Playwright
    └── utils/
        └── keyboards.py     # القوائم والأزرار
```

---

## 🚀 النشر على Railway (الطريقة الموصى بها)

### الخطوة 1 — تجهيز ملفات البوت
1. فك ضغط الملف وارفعه على مستودع GitHub خاص.

### الخطوة 2 — إنشاء مشروع Railway
1. ادخل على [railway.app](https://railway.app) وسجّل دخول.
2. اضغط **New Project → Deploy from GitHub repo**.
3. اختر المستودع الذي رفعت إليه الكود.
4. سينتقي Railway الـ `Dockerfile` تلقائياً.

### الخطوة 3 — إضافة قاعدة بيانات PostgreSQL
1. داخل المشروع، اضغط **+ New → Database → PostgreSQL**.
2. سيتم إنشاء متغير `DATABASE_URL` تلقائياً.
3. **مهم:** اربط الـ DB بخدمة البوت:
   - في خدمة البوت → `Variables` → اضغط `Add Reference` واختر `DATABASE_URL` من قاعدة البيانات.

### الخطوة 4 — إضافة المتغيرات
داخل خدمة البوت → `Variables` → أضف:

```env
BOT_TOKEN=ضع_توكن_البوت_من_BotFather
ADMIN_IDS=معرّفك_في_تلجرام
WEBAPP_URL=https://رابط-الواجهة-المنشورة
SHEERID_POLL_MINUTES=15
```

> 💡 **كيف تجلب معرّفك؟** أرسل `/start` لـ [@userinfobot](https://t.me/userinfobot).

### الخطوة 5 — نشر الـ WebApp (`webapp/index.html`)

البوت يحتاج رابط HTTPS عام للواجهة. اختر طريقة:

**الطريقة الأسهل — GitHub Pages:**
1. أنشئ مستودع جديد باسم `pixel-webapp`.
2. ارفع داخله ملف `webapp/index.html` باسم `index.html`.
3. اذهب إلى Settings → Pages → فعّل من `main`.
4. الرابط سيكون: `https://your-username.github.io/pixel-webapp/`
5. ضع هذا الرابط في `WEBAPP_URL` على Railway.

**أو على Netlify (drag & drop):**
1. ادخل [app.netlify.com/drop](https://app.netlify.com/drop)
2. اسحب مجلد `webapp/` كاملاً.
3. انسخ الرابط الذي يعطيك إياه.

### الخطوة 6 — التشغيل
سيشغّل Railway البوت تلقائياً. راقب الـ Logs، يجب أن ترى:
```
Bot connected: @your_bot_username
Polling is active
```

---

## ⚙️ المتغيرات الكاملة

| المتغير | القيمة الافتراضية | الوصف |
|---------|------------------|-------|
| `BOT_TOKEN` | (مطلوب) | توكن البوت من BotFather |
| `ADMIN_IDS` | (مطلوب) | معرّفات الأدمنز مفصولة بفاصلة |
| `DATABASE_URL` | (مطلوب) | رابط PostgreSQL |
| `WEBAPP_URL` | (مطلوب) | رابط HTTPS لـ `webapp/index.html` |
| `SHEERID_POLL_MINUTES` | `15` | مدة انتظار قرار SheerID |
| `SHEERID_POLL_INTERVAL` | `10` | فاصل الاستعلام بالثواني |
| `DEFAULT_CREDITS` | `3` | رصيد المستخدم الجديد |
| `VERIFY_COST` | `1` | تكلفة عملية تحقق |
| `CHECKIN_REWARD` | `1` | مكافأة الحضور اليومي |
| `REFERRAL_BONUS` | `2` | مكافأة الدعوة |
| `BROWSER_PROVIDER` | `""` | `browserless` / `browserbase` / فارغ |
| `BROWSERLESS_TOKEN` | — | إذا اخترت Browserless |
| `BROWSERBASE_API_KEY` | — | إذا اخترت BrowserBase |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` |

---

## 💡 حل مشكلة `SheerID لم يوافق خلال 5 دقائق (pending)`

السبب الأرجح أن SheerID وضع طلبك في طابور المراجعة اليدوية بسبب:
1. **بصمة المتصفح / IP مكشوفة** — الحل: استخدم `BROWSER_PROVIDER=browserless` مع بروكسي سكني.
2. **مدة الانتظار قصيرة** — تم إصلاحها: زِد `SHEERID_POLL_MINUTES` إلى 20-30.
3. **بيانات وهمية يكشفها SheerID** — تأكد أن أسماء الجامعات الموجودة في `bot/services/sheerid.py` حقيقية وحديثة.

```env
# للحصول على أفضل النتائج:
BROWSER_PROVIDER=browserless
BROWSERLESS_TOKEN=your_token
BROWSERLESS_PROXY=residential
BROWSERLESS_PROXY_COUNTRY=us
SHEERID_POLL_MINUTES=20
```

---

## 🛠️ التشغيل المحلي (للتطوير)

```bash
pip install -r requirements.txt
playwright install chromium
python -m camoufox fetch              # متصفح مضاد للكشف (مجاني)

cp .env.example .env                  # عدّل القيم
python -m bot.main
```

---

## 🐳 Docker

```bash
docker build -t merged-tgbot .
docker run --env-file .env merged-tgbot
```

---

## 📞 أوامر المستخدم والأدمن

### المستخدم
- `/start` — القائمة الرئيسية
- `/pixel` — فتح نموذج Google One (WebApp)
- `/ping`, `/me`, `/ref`, `/qd`, `/use <كود>`, `/help`

### الأدمن
- `/admin`, `/stats`, `/addcredit`, `/ban`, `/unban`, `/blacklist`
- `/broadcast`, `/genkey`, `/listkeys`, `/addcard`, `/cards`, `/delcard`

---

## 📝 سجل التغييرات

### الإصدار الحالي
- ✅ زيادة مدة انتظار SheerID من 5 → 15 دقيقة (قابلة للتعديل)
- ✅ إضافة `.env.example` و `.gitignore`
- ✅ توثيق نشر Railway مفصّل بالعربية
- ✅ إصلاح رسالة الخطأ لتعكس المدة الفعلية
