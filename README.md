# 🤖 SheerID Telegram Bot

بوت تلجرام كامل يُغلّف أدوات التحقق من **SheerID** السبعة (Spotify, YouTube, Google One, Bolt.new, K12 ChatGPT, Veterans, Perplexity)، ويعمل مع قاعدة بيانات **PostgreSQL** على **Railway**، وجاهز للنشر المباشر من **GitHub**.

---

## ✨ المزايا

- 🎯 **7 خدمات تحقق** جاهزة في واجهة واحدة
- 🔘 **أزرار تفاعلية** + كشف تلقائي لنوع الخدمة من الرابط
- 💎 **نظام رصيد** (3 عمليات مجانية لكل مستخدم جديد)
- 🎁 **نظام إحالة** (+5 رصيد لكل دعوة ناجحة)
- 🛠 **لوحة أدمن** كاملة (إحصائيات / حظر / إضافة رصيد / بث جماعي)
- 📊 **سجل كامل** لكل عمليات التحقق في PostgreSQL
- 🚀 **نشر بنقرة واحدة** على Railway

---

## 📋 المتطلبات

1. **توكن بوت** من [@BotFather](https://t.me/BotFather) على تلجرام
2. **معرّف تلجرامي** الخاص بك (احصل عليه من [@userinfobot](https://t.me/userinfobot))
3. حساب على [GitHub](https://github.com)
4. حساب على [Railway](https://railway.app)

---

## 🚀 خطوات النشر على Railway (أسهل طريقة)

### 1️⃣ ارفع المشروع إلى GitHub

```bash
# فك ضغط الملف ثم:
cd sheerid-telegram-bot
git init
git add .
git commit -m "Initial commit: SheerID Telegram Bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/sheerid-telegram-bot.git
git push -u origin main
```

### 2️⃣ أنشئ مشروع Railway

1. اذهب إلى [railway.app](https://railway.app) واضغط **New Project**
2. اختر **Deploy from GitHub repo**
3. حدّد ريبو `sheerid-telegram-bot`

### 3️⃣ أضف قاعدة بيانات PostgreSQL

1. داخل المشروع: **+ New** → **Database** → **Add PostgreSQL**
2. Railway سينشئ متغيّر `DATABASE_URL` تلقائياً ويربطه بالخدمة ✅

### 4️⃣ أضف متغيّرات البيئة

في تبويب **Variables** للخدمة، أضف:

| المتغيّر | القيمة |
|----------|--------|
| `BOT_TOKEN` | التوكن من @BotFather |
| `ADMIN_IDS` | معرّفك التلجرامي (مفصولة بفواصل لو أكثر من واحد) |
| `DEFAULT_CREDITS` | `3` (اختياري) |
| `REFERRAL_BONUS` | `5` (اختياري) |

> ✅ `DATABASE_URL` موجود تلقائياً من خطوة 3 — لا تكتبه يدوياً.

### 5️⃣ Deploy 🎉

- Railway سيبدأ البناء تلقائياً
- بعد دقيقة افتح **Logs** وابحث عن:
  ```
  ✅ قاعدة البيانات جاهزة (الجداول مُنشأة).
  🤖 البوت يعمل: @your_bot
  🚀 بدء polling…
  ```
- اذهب إلى البوت في تلجرام وأرسل `/start`

---

## 🖥️ التشغيل المحلي (للتجربة)

```bash
# 1. ثبّت بايثون 3.11+
python --version

# 2. أنشئ بيئة افتراضية
python -m venv .venv
source .venv/bin/activate    # على Windows: .venv\Scripts\activate

# 3. ثبّت المتطلبات
pip install -r requirements.txt

# 4. أنشئ .env من القالب
cp .env.example .env
# عدّل القيم داخل .env

# 5. شغّل البوت
python -m bot.main
```

> 💡 PostgreSQL محلياً: ثبّت Docker ثم:
> ```bash
> docker run -d --name pg -e POSTGRES_PASSWORD=secret -p 5432:5432 postgres:16
> ```
> ثم في `.env`: `DATABASE_URL=postgresql://postgres:secret@localhost:5432/postgres`

---

## 📁 هيكل المشروع

```
sheerid-telegram-bot/
├── bot/
│   ├── main.py                # نقطة التشغيل + polling
│   ├── config.py              # قراءة المتغيرات البيئية
│   ├── handlers/              # معالجات الأوامر
│   │   ├── start.py           # /start, القائمة
│   │   ├── verify.py          # تنفيذ التحقق
│   │   └── admin.py           # أوامر الأدمن
│   ├── services/              # محرّكات SheerID
│   │   ├── __init__.py        # سجل الخدمات + التشغيل
│   │   └── originals/         # السكربتات الأصلية (دون أي تعديل)
│   │       ├── spotify_main.py
│   │       ├── youtube_main.py
│   │       ├── google_one_main.py
│   │       ├── boltnew_main.py
│   │       ├── k12_main.py
│   │       ├── veterans_main.py
│   │       └── perplexity_main.py
│   ├── db/
│   │   ├── connection.py      # asyncpg pool + migrations
│   │   ├── models.py          # CRUD users/verifications/referrals
│   │   └── migrations.sql
│   └── utils/
│       └── keyboards.py       # أزرار تلجرام
├── requirements.txt
├── Procfile                   # worker: python -m bot.main
├── railway.json               # إعدادات Railway
├── nixpacks.toml              # إعدادات البناء
├── runtime.txt                # python-3.11.9
├── .env.example
├── .gitignore
└── README.md
```

---

## 💬 أوامر البوت

### للمستخدم
| الأمر | الوصف |
|------|-------|
| `/start` | البدء + القائمة الرئيسية |
| `/me` | عرض حسابي ورصيدي |
| `/ref` | رابط الدعوة الخاص بي |
| `/help` | المساعدة |

### للأدمن (`ADMIN_IDS` فقط)
| الأمر | الوصف |
|------|-------|
| `/admin` | لوحة الأدمن |
| `/stats` | إحصائيات شاملة |
| `/addcredit <user_id> <amount>` | إضافة رصيد |
| `/ban <user_id>` | حظر مستخدم |
| `/unban <user_id>` | رفع الحظر |
| `/broadcast <message>` | بث رسالة لكل المستخدمين |

---

## 🗄️ مخطط قاعدة البيانات

تُنشأ الجداول تلقائياً عند أول تشغيل:

- `users` — المستخدمون والرصيد والإحصائيات
- `verifications` — سجل كل عمليات التحقق
- `referrals` — سجل الإحالات

ملف SQL: `bot/db/migrations.sql`.

---

## 🛠️ كيف يعمل البوت داخلياً؟

البوت **لا يُعيد كتابة منطق التحقق** — بل يُشغّل سكربتات Python الأصلية الموجودة في `bot/services/originals/` كعمليات فرعية، تماماً كما تُستخدم من سطر الأوامر:

```python
python originals/spotify_main.py "https://services.sheerid.com/verify/..."
```

هذا يضمن:
- ✅ بقاء كل المنطق المعقّد (توليد الهويات، اختيار الجامعات، رفع الوثائق) كما هو
- ✅ سهولة تحديث أي خدمة بنسخ نسخة أحدث من السكربت الأصلي

---

## 🔒 الأمان

- ⚠️ لا ترفع ملف `.env` إلى GitHub أبداً (محمي في `.gitignore`)
- ⚠️ ضع `BOT_TOKEN` في Railway Variables فقط
- ⚠️ احتفظ بمعرّفك في `ADMIN_IDS` لمنع وصول الآخرين للوحة الأدمن

---

## 📜 الترخيص

هذا البوت مبني على [SheerID-Verification-Tool](https://github.com/ThanhNguyxn/SheerID-Verification-Tool) المرخّص بـ MIT.
