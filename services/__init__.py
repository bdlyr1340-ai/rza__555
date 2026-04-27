"""سجلّ الخدمات وآلية تشغيلها.

كل خدمة هي ملف `*_main.py` أصلي من المشروع المرفوع. نحن لا نُعيد كتابة منطق
التحقق — بل نشغّل السكربت الأصلي كسكربت فرعي ونمرّر له رابط SheerID كحجة
سطر أوامر، تماماً مثل الاستخدام الأصلي:

    python originals/spotify_main.py <SHEERID_URL>

هذا يضمن بقاء كل المنطق المعقد (توليد الهويات، اختيار الجامعات، رفع الوثائق…)
كما هو دون أي خطر من الكسر أثناء النقل.
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger(__name__)

ORIGINALS_DIR = Path(__file__).parent / "originals"


@dataclass
class ServiceMeta:
    key: str
    label: str
    script: str           # اسم الملف داخل originals/
    description: str
    url_hints: list       # كلمات مفتاحية في رابط SheerID للكشف التلقائي

    def asdict(self):
        return {
            "key": self.key, "label": self.label, "script": self.script,
            "description": self.description,
        }


# ترتيب العناصر = ترتيب الأزرار
_SERVICES = [
    ServiceMeta("spotify",    "🎵 Spotify Premium",
                "spotify_main.py",
                "تحقق طالب جامعي لاشتراك Spotify Premium",
                ["spotify"]),
    ServiceMeta("youtube",    "🎬 YouTube Premium",
                "youtube_main.py",
                "تحقق طالب جامعي لاشتراك YouTube Premium",
                ["youtube", "google"]),
    ServiceMeta("google_one", "🤖 Google One / Gemini",
                "google_one_main.py",
                "تحقق طالب جامعي لاشتراك Google One AI",
                ["googleone", "gemini", "google-one"]),
    ServiceMeta("boltnew",    "👨‍🏫 Bolt.new (معلم)",
                "boltnew_main.py",
                "تحقق معلم جامعي لخدمة Bolt.new",
                ["bolt"]),
    ServiceMeta("k12",        "🏫 K12 ChatGPT Plus",
                "k12_main.py",
                "تحقق معلم K12 لاشتراك ChatGPT Plus",
                ["openai", "chatgpt", "k12"]),
    ServiceMeta("veterans",   "🎖️ Veterans (عسكري)",
                "veterans_main.py",
                "تحقق حالة عسكرية / متقاعد",
                ["veteran", "military"]),
    ServiceMeta("perplexity", "🔍 Perplexity Pro",
                "perplexity_main.py",
                "تحقق طالب لاشتراك Perplexity Pro",
                ["perplexity"]),
]

SERVICE_REGISTRY: Dict[str, dict] = {s.key: s.asdict() for s in _SERVICES}
_BY_KEY = {s.key: s for s in _SERVICES}


def detect_service_from_url(url: str) -> Optional[str]:
    """يحاول كشف نوع الخدمة من رابط SheerID."""
    u = url.lower()
    for s in _SERVICES:
        for hint in s.url_hints:
            if hint in u:
                return s.key
    return None


SHEERID_URL_RE = re.compile(r"https?://[^\s]*sheerid[^\s]*", re.IGNORECASE)


def extract_sheerid_url(text: str) -> Optional[str]:
    if not text:
        return None
    m = SHEERID_URL_RE.search(text)
    return m.group(0) if m else None


@dataclass
class RunResult:
    success: bool
    output: str           # آخر ~50 سطر من stdout/stderr للعرض
    error: Optional[str] = None


async def run_verification(service_key: str, sheerid_url: str, timeout: int = 240) -> RunResult:
    """يشغّل سكربت التحقق الأصلي ويُعيد النتيجة.

    نعتمد على Python نفسه الذي يشغّل البوت، ونمرّر رابط SheerID كحجة.
    """
    meta = _BY_KEY.get(service_key)
    if not meta:
        return RunResult(False, "", f"خدمة غير معروفة: {service_key}")

    script_path = ORIGINALS_DIR / meta.script
    if not script_path.exists():
        return RunResult(False, "", f"ملف السكربت مفقود: {script_path}")

    log.info("▶️ تشغيل %s لـ %s", meta.script, sheerid_url)

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path), sheerid_url,
            cwd=str(ORIGINALS_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={"PYTHONUNBUFFERED": "1", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
    except Exception as e:
        return RunResult(False, "", f"تعذّر تشغيل السكربت: {e}")

    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return RunResult(False, "", "انتهى الوقت المحدد للعملية ⏱️")

    raw = (stdout or b"").decode("utf-8", errors="replace")
    tail = "\n".join(raw.strip().splitlines()[-40:])

    rc = proc.returncode or 0
    success_markers = ("✅", "success", "approved", "completed", "auto-approved")
    failure_markers = ("❌", "failed", "rejected", "error", "denied")

    text_lower = raw.lower()
    if rc == 0 and any(m in text_lower or m in raw for m in success_markers) \
            and not any(m in raw for m in ("❌",)):
        return RunResult(True, tail)
    if rc != 0 or any(m in text_lower for m in failure_markers):
        return RunResult(False, tail, f"rc={rc}")
    # افتراضياً اعتمد على رمز الخروج
    return RunResult(rc == 0, tail, None if rc == 0 else f"rc={rc}")
