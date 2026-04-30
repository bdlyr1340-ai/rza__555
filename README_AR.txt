رضا، هذا التصحيح الجديد لا يحتوي ملفات كاملة من مشروعك.
لا تستبدل به أي مجلد كامل.

اسم التصحيح:
rza_counter_screenshot_patch_v3.zip

المحتوى:
- tools/apply_counter_screenshot_patch.py
- docs/MANUAL_PATCH.txt
- docs/WHAT_CHANGED.txt
- bot/utils/admin_screenshot_sender.py  ← اختياري فقط، لا تحتاجه للتطبيق

طريقة التطبيق:
1) فك الضغط داخل مجلد مشروع البوت الرئيسي، نفس المكان الذي يحتوي مجلد bot.
2) شغّل:
   python tools/apply_counter_screenshot_patch.py
3) السكربت يسوي نسخة احتياطية تلقائياً:
   bot/handlers/start.py.bak_counter_screenshot_v3

مهم جداً:
- لا ترفع ملف start.py كامل من هذا التصحيح لأنه غير موجود أصلاً.
- لا تستبدل bot/services/sheerid.py.
- هذا التصحيح يلمس bot/handlers/start.py فقط.

بعد التطبيق:
- العداد يتحرك كل ثانية.
- العلامات تكون:
  ⬜ انتظار
  🔄 جاري
  🟩 نجاح
  🟥 خطأ
- الأدمن يستلم لقطة شاشة فقط، بدون HTML وبدون تفاصيل قديمة.
