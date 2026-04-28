"""Service registry and URL helpers."""
from __future__ import annotations

import re
from typing import Dict, Any, Optional

SERVICE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "google_one": {
        "label": "Google One / Gemini Pro",
        "description": "تحقق طلابي لاشتراك جوجل ون وجيمناي برو سنوي",
        "program_id": "67a5e7a0c522e014ce117d93",
    },
    "spotify": {
        "label": "Spotify Student",
        "description": "تحقق طلابي لاشتراك سبوتيفاي بريميوم للطلاب",
        "program_id": "5edfe14d2ebf3e21a06c8860",
    },
    "youtube": {
        "label": "YouTube Student Premium",
        "description": "تحقق طلابي لاشتراك يوتيوب بريميوم للطلاب",
        "program_id": "6329bb1ed3c7ae38b4c24fb3",
    },
    "boltnew": {
        "label": "Bolt.new Teacher",
        "description": "تحقق للمعلمين — يعطي كود تفعيل",
        "program_id": "",
    },
    "k12": {
        "label": "ChatGPT Teacher K12",
        "description": "تحقق للمعلمين K12 — اشتراك ChatGPT",
        "program_id": "",
    },
    "perplexity": {
        "label": "Perplexity Student",
        "description": "تحقق طلابي لاشتراك Perplexity Pro",
        "program_id": "",
    },
    "veterans": {
        "label": "Veterans / Military",
        "description": "تحقق عسكري / محاربين قدامى",
        "program_id": "",
    },
}

_URL_PATTERNS: Dict[str, list] = {
    "spotify": ["spotify"],
    "youtube": ["youtube", "music.youtube"],
    "google_one": ["one.google", "gemini"],
    "boltnew": ["bolt.new", "stackblitz"],
    "k12": ["k12", "chatgpt"],
    "perplexity": ["perplexity"],
    "veterans": ["veteran", "military"],
}


def detect_service_from_url(url: str) -> Optional[str]:
    url_lower = url.lower()
    for svc, keywords in _URL_PATTERNS.items():
        if any(kw in url_lower for kw in keywords):
            return svc
    return None


def extract_sheerid_url(text: str) -> Optional[str]:
    m = re.search(r"(https?://[^\s]+sheerid[^\s]+)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"(https?://[^\s]*verificationId=[^\s]+)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None
