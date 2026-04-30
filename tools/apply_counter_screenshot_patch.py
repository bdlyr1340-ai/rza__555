from __future__ import annotations

from pathlib import Path
import re
import shutil
import sys

ROOT = Path.cwd()
START = ROOT / "bot" / "handlers" / "start.py"

if not START.exists():
    print("❌ ما لقيت bot/handlers/start.py — شغّل السكربت من داخل مجلد مشروع البوت الرئيسي.")
    sys.exit(1)

text = START.read_text(encoding="utf-8")
original = text

backup = START.with_suffix(".py.bak_counter_screenshot_v3")
if not backup.exists():
    shutil.copy2(START, backup)
    print(f"✅ تم إنشاء نسخة احتياطية: {backup}")
else:
    print(f"ℹ️ النسخة الاحتياطية موجودة سابقاً: {backup}")

# 1) import os فقط حتى نتحقق من وجود ملف لقطة النجاح.
if "import os\n" not in text:
    if "import time\n" in text:
        text = text.replace("import time\n", "import time\nimport os\n", 1)
    elif "import logging\n" in text:
        text = text.replace("import logging\n", "import logging\nimport os\n", 1)
    else:
        text = "import os\n" + text

# 2) استبدال دالة عرض التقدم فقط: العداد + العلامات.
new_build_func = '''def _build_pixel_progress(gmail: str, current_step: int, elapsed_secs: float,
                           success: bool = False, error: str = "") -> str:
    """Build 10-step progress text. Only UI: timer + square status icons."""
    total_steps = len(_STEP_NAMES)
    current_step = max(0, min(int(current_step), total_steps))

    lines = ["🤖 Pixel Automation", f"📧 {gmail}", "────────────────────────"]
    for i, name in enumerate(_STEP_NAMES):
        step_num = i + 1
        if success or i < current_step:
            icon = "🟩"
        elif error and i == current_step:
            icon = "🟥"
        elif i == current_step and not error:
            icon = "🔄"
        else:
            icon = "⬜"
        lines.append(f"{icon} {step_num:>2}. {name}")

    lines.append("────────────────────────")
    if success:
        lines.append("🎉 Success!")
    elif error:
        lines.append(f"❌ {error}")

    elapsed_int = max(0, int(elapsed_secs))
    mins = elapsed_int // 60
    secs = elapsed_int % 60
    lines.append(f"⏱ Elapsed: {mins:02d}:{secs:02d}")
    return "\\n".join(lines)


'''
pattern = r"def _build_pixel_progress\([\s\S]*?\n\n# ────────────── WebApp data handler"
match = re.search(pattern, text)
if match:
    text = re.sub(pattern, new_build_func + "# ────────────── WebApp data handler", text, count=1)
else:
    print("❌ ما قدرت ألقى دالة _build_pixel_progress حتى أبدلها. ما غيرت هذا الجزء.")
    sys.exit(2)

# 3) نخلي الوقت monotonic حتى العداد يبقى صحيح حتى لو صار تغيير بساعة السيرفر.
text = text.replace("start_time = time.time()", "start_time = time.monotonic()")
text = text.replace("time.time() - start_time", "time.monotonic() - start_time")

# 4) التحديث كل ثانية بدل 3 ثواني. هذا فقط داخل الملف، وإذا كان مطبق سابقاً ما يضر.
text = text.replace("# ── Background ticker — refreshes elapsed time every 3 seconds ──", "# ── Background ticker — refreshes elapsed time every 1 second ──")
text = text.replace("await asyncio.sleep(3)\n                elapsed = time.monotonic() - start_time", "await asyncio.sleep(1)\n                elapsed = time.monotonic() - start_time")
text = text.replace("await asyncio.sleep(3)\n                elapsed = time.time() - start_time", "await asyncio.sleep(1)\n                elapsed = time.monotonic() - start_time")

# 5) لقطة الشاشة: فشل من debug القديم، نجاح من /tmp/gemini_claim_page.png الموجود أصلاً بالكود القديم.
old_path_line = '        screenshot_path = debug.get("screenshot") or ""\n'
new_path_block = '''        screenshot_path = debug.get("screenshot") or result.get("screenshot") or ""
        if result.get("success") and not screenshot_path:
            success_candidate = "/tmp/gemini_claim_page.png"
            if os.path.exists(success_candidate):
                screenshot_path = success_candidate
'''
if old_path_line in text:
    text = text.replace(old_path_line, new_path_block, 1)
elif 'success_candidate = "/tmp/gemini_claim_page.png"' in text:
    print("ℹ️ مسار لقطة النجاح موجود سابقاً.")
else:
    print("⚠️ ما لقيت سطر screenshot_path القديم؛ كملت باقي التعديلات فقط.")

# 6) لا نرسل HTML ولا تفاصيل قديمة — لقطة الشاشة فقط.
text = text.replace('        summary = debug.get("summary") or ""\n', '        summary = ""  # لقطة فقط: لا ترسل تفاصيل الصفحة\n')
text = text.replace('        html_path = debug.get("html") or ""\n', '        html_path = ""  # لقطة فقط: لا ترسل HTML\n')

# 7) كابشن اللقطة يكون نجاح/خطأ حسب النتيجة.
old_caption = 'caption=f"📸 لقطة صفحة Google التي رفضت الدخول (طلب #{ver_id})",'
new_caption = 'caption=(\n                                    f"📸 لقطة {\'نجاح\' if result.get(\'success\') else \'خطأ\'} للطلب #{ver_id}"\n                                ),'
if old_caption in text:
    text = text.replace(old_caption, new_caption, 1)

if text == original:
    print("ℹ️ ماكو تغيير جديد — يمكن التعديلات مطبقة سابقاً.")
else:
    START.write_text(text, encoding="utf-8")
    print("✅ تم تطبيق التصحيح على bot/handlers/start.py فقط.")
    print("✅ العداد صار يتحدث كل ثانية.")
    print("✅ العلامات: ⬜ انتظار / 🔄 جاري / 🟩 نجاح / 🟥 خطأ.")
    print("✅ الأدمن يستلم لقطة فقط عند الخطأ أو النجاح إذا اللقطة موجودة.")
    print("✅ لم يتم لمس bot/services/sheerid.py ولا أي ملف ثاني.")
