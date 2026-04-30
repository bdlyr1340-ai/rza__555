# تحديث v5 — العداد + التشخيص

  ## الملفان (نفسهما كل مرة)
  1. `bot/handlers/start.py`  ← **الأهم** (إصلاح العداد)
  2. `bot/services/sheerid.py` ← (سرعة + Authenticator)

  ## كيف ترفعها على Railway
  1. افتح GitHub → مستودع البوت
  2. ادخل لمجلد `bot/handlers/` → اضغط على `start.py` → علامة القلم (Edit)
  3. **امسح كل المحتوى** → الصق محتوى `start.py` الجديد من هذا الملف
  4. Commit changes
  5. كرّر نفس الخطوات لـ `bot/services/sheerid.py`
  6. Railway سيعمل Redeploy تلقائياً (انتظر ~1 دقيقة)

  ---

  ## ⏱ كيف تتأكد أن العداد سيعمل بعد الرفع

  ### علامة 1: في الكود
  افتح ملف `start.py` على GitHub بعد الرفع وابحث عن:
  ```
  TICKER STARTED
  ```
  لو موجود → ✅ الملف الجديد مرفوع.

  ### علامة 2: في Logs على Railway
  بعد الرفع، اذهب لـ Railway → web → **View Logs** ← هذا مهم جداً.

  عندما تجرّب البوت، يجب أن ترى في الـ logs أسطراً مثل:
  ```
  ⏱ Ticker task created: <Task pending ...>
  ⏱ TICKER STARTED for nefujifil305@gmail.com
  ⏱ TICK #1 elapsed=2.0s step=0
  ⏱ TICK #6 elapsed=12.0s step=2
  ⏱ TICK #11 elapsed=22.0s step=3
  ```

  **أرسل لي صورة من هذه الـ logs لو العداد لم يتحرّك** —
  سأعرف من خلالها بالضبط أين المشكلة:
  - لو رأيت "TICKER STARTED" لكن لم تتحرّك الأرقام → مشكلة في تيليجرام
  - لو لم ترَ "TICKER STARTED" → الملف القديم مازال يعمل
  - لو رأيت "TICKER edit failed" → سأعرف السبب الحقيقي

  ---

  ## ما الجديد في v5

  ### العداد
  - يحدّث كل **2 ثانية** (بدلاً من 3) → أكثر استجابة
  - يستخدم `ctx.bot.edit_message_text` مباشرة (أكثر استقراراً)
  - يطبع في الـ logs كل 10 ثوانٍ ليثبت أنه يعمل
  - يطبع سبب أي فشل ليساعدنا في التشخيص

  ### السرعة
  متغيّر `SHEERID_SPEED_FACTOR` افتراضياً 0.4 (أسرع 2.5×).
  ضع `0.25` للسرعة القصوى.

  ### Authenticator
  يضغط على خيار `<li>` و `<div role="link">` بنجاح.

  ---

  ## ⚠️ تنبيه مهم
  لو رفعت v4 سابقاً ثم رفعت v5 الآن، **انتظر دقيقتين** بعد الـ Commit
  لتتأكد أن Railway أكمل الـ Build و الـ Deploy. لا تجرّب البوت قبل
  أن ترى "Deployment successful" في Railway.
  