"""سجل الخدمات والأزرار."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ServiceMeta:
    key: str
    label: str
    script: str
    description: str
    url_hints: list[str]

    def asdict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "script": self.script,
            "description": self.description,
        }


# ترتيب العناصر = ترتيب الأزرار
_SERVICES = [
    ServiceMeta("spotify", "🎵 سبوتيفاي بريميوم", "spotify_main.py", "خدمة سبوتيفاي بريميوم", ["spotify"]),
    ServiceMeta("youtube", "🎬 يوتيوب بريميوم", "youtube_main.py", "خدمة يوتيوب بريميوم", ["youtube"]),
    ServiceMeta("google_one", "🤖 جوجل ون / جيمناي", "google_one_main.py", "خدمة Google One / Gemini", ["googleone", "gemini", "google-one", "google"]),
    ServiceMeta("boltnew", "👨‍🏫 بولت للمعلمين", "boltnew_main.py", "خدمة Bolt.new", ["bolt"]),
    ServiceMeta("k12", "🏫 ChatGPT K12", "k12_main.py", "خدمة ChatGPT K12", ["openai", "chatgpt", "k12"]),
    ServiceMeta("veterans", "🎖️ العسكريين / المتقاعدين", "veterans_main.py", "خدمة العسكريين والمتقاعدين", ["veteran", "military"]),
    ServiceMeta("perplexity", "🔍 بيربلكسيتي برو", "perplexity_main.py", "خدمة Perplexity Pro", ["perplexity"]),
]

SERVICE_REGISTRY: Dict[str, dict] = {s.key: s.asdict() for s in _SERVICES}
_BY_KEY = {s.key: s for s in _SERVICES}
SHEERID_URL_RE = re.compile(r"https?://[^\s]*sheerid[^\s]*", re.IGNORECASE)


# Map SheerID program IDs to service keys
_PROGRAM_ID_MAP: Dict[str, str] = {
    "67c8c14f5f17a83b745e3f82": "spotify",
    "68cc6a2e64f55220de204448": "boltnew",
    "68d47554aa292d20b9bec8f7": "k12",
    "690415d58971e73ca187d8c9": "veterans",
}

_PROGRAM_ID_RE = re.compile(r"/verify/([a-f0-9]{24,})", re.IGNORECASE)


def detect_service_from_url(url: str) -> Optional[str]:
    # First try to match program ID from the URL path
    pid_match = _PROGRAM_ID_RE.search(url)
    if pid_match:
        pid = pid_match.group(1)
        if pid in _PROGRAM_ID_MAP:
            return _PROGRAM_ID_MAP[pid]
    # Fallback to keyword hints
    u = url.lower()
    for s in _SERVICES:
        for hint in s.url_hints:
            if hint in u:
                return s.key
    return None


def extract_sheerid_url(text: str) -> Optional[str]:
    if not text:
        return None
    m = SHEERID_URL_RE.search(text)
    return m.group(0) if m else None
