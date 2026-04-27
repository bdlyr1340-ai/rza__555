# 📦 دليل النشر السريع على Railway

دليل مختصر بالخطوات. للتفاصيل الكاملة راجع `README.md`.

---

## ✅ Checklist قبل البدء

- [ ] حساب GitHub
- [ ] حساب Railway (سجّل عبر GitHub)
- [ ] توكن بوت من [@BotFather](https://t.me/BotFather)
- [ ] معرّفك التلجرامي من [@userinfobot](https://t.me/userinfobot)

---

## 1. إنشاء البوت في تلجرام

1. افتح [@BotFather](https://t.me/BotFather)
2. أرسل `/newbot`
3. اختر اسم البوت (مثل: My SheerID Bot)
4. اختر username (يجب أن ينتهي بـ `bot`، مثل: `my_sheerid_bot`)
5. ✅ ستحصل على توكن بهذا الشكل: `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
6. **احتفظ به** — ستحتاجه في Railway

---

## 2. رفع الكود إلى GitHub

```bash
# داخل مجلد المشروع
git init
git add .
git commit -m "Initial commit"
git branch -M main

# أنشئ ريبو فارغ على GitHub باسم sheerid-telegram-bot، ثم:
git remote add origin https://github.com/YOUR_USERNAME/sheerid-telegram-bot.git
git push -u origin main
```

---

## 3. النشر على Railway

### أ. أنشئ المشروع
1. [railway.app](https://railway.app) → **New Project**
2. **Deploy from GitHub repo** → اختر `sheerid-telegram-bot`
3. Railway سيبدأ البناء (سيفشل أول مرة لأن المتغيرات غير معدّة — هذا طبيعي)

### ب. أضف PostgreSQL
1. داخل المشروع اضغط **+ New** (يمين أعلى)
2. **Database** → **Add PostgreSQL**
3. ✅ تم — `DATABASE_URL` متاح الآن لكل خدمات المشروع

### ج. اضبط المتغيرات
1. اضغط على خدمة البوت
2. تبويب **Variables**
3. أضف:
   - `BOT_TOKEN` = توكنك من BotFather
   - `ADMIN_IDS` = معرّفك (مثل `123456789`)

### د. إعادة النشر
- اضغط **Deployments** → آخر deployment → **Redeploy**
- أو ادفع أي commit جديد إلى GitHub (Railway سيعيد النشر تلقائياً)

---

## 4. التحقق من العمل

1. افتح تبويب **Deploy Logs** للخدمة
2. ابحث عن:
   ```
   ✅ قاعدة البيانات جاهزة (الجداول مُنشأة).
   🤖 البوت يعمل: @your_bot_username
   🚀 بدء polling…
   ```
3. افتح بوتك في تلجرام وأرسل `/start` 🎉

---

## ❗ حل المشاكل الشائعة

| المشكلة | الحل |
|---------|------|
| `BOT_TOKEN is required` | راجع تبويب Variables — ربما نسيت الإضافة |
| `connection refused` لقاعدة البيانات | تأكد من إضافة PostgreSQL plugin وأنه ضمن نفس المشروع |
| البوت يعمل لكن لا يرد | تأكد أنك بدأته بـ `/start` وأن التوكن صحيح |
| `Conflict: terminated by other getUpdates` | لديك نسخة أخرى من البوت تعمل بنفس التوكن — أوقفها |
| `/admin` لا يعمل | تأكد أن معرّفك مكتوب في `ADMIN_IDS` بدون مسافات |

---

## 💰 تكلفة Railway

- خطة Hobby المجانية: **$5 رصيد شهري** (يكفي لبوت متوسط الحجم)
- البوت + PostgreSQL يستهلكان حوالي $3-4/شهر تقريباً
