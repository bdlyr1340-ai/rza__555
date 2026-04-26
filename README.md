# Telegram Railway GitHub Bot

بوت تلگرام آمن يدعم العربية والإنكليزية، متصل بقاعدة بيانات Railway PostgreSQL، ومعه ربط اختياري بـ GitHub Issues.

> ملاحظة: لم يتم تضمين أو تحويل أي كود مخصص لتجاوز أنظمة تحقق أو توليد وثائق. هذا المشروع لإدارة الطلبات والحفظ والمتابعة فقط.

## المميزات
- أزرار تلگرام: طلب جديد، طلباتي، تغيير اللغة.
- دعم عربي/إنكليزي.
- حفظ المستخدمين والطلبات داخل PostgreSQL على Railway.
- إنشاء GitHub Issue تلقائي لكل طلب إذا أضفت إعدادات GitHub.
- أمر `/admin` للإحصائيات للمشرفين فقط.

## التشغيل المحلي
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

## متغيرات البيئة
ضعها داخل Railway Variables أو ملف `.env`:

```env
BOT_TOKEN=توكن_البوت
ADMIN_IDS=ايديك_تلگرام
DATABASE_URL=رابط_PostgreSQL_من_Railway
GITHUB_TOKEN=توكن_GitHub_اختياري
GITHUB_OWNER=اسم_الحساب_او_المنظمة
GITHUB_REPO=اسم_المستودع
DEFAULT_LANG=ar
```

## النشر على Railway
1. ارفع الملفات على GitHub.
2. افتح Railway واختر New Project.
3. أضف PostgreSQL.
4. أضف Variables أعلاه.
5. اربط GitHub repo أو ارفع المشروع.
6. Railway سيشغّل الأمر:
```bash
python -m bot.main
```

## حقول GitHub المستخدمة
- `GITHUB_TOKEN`
- `GITHUB_OWNER`
- `GITHUB_REPO`

البوت ينشئ Issue بعنوان الطلب ويضع ملاحظة المستخدم داخله، ثم يحفظ رقم الـ Issue بقاعدة البيانات.
