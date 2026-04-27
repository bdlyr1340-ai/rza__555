"""Service registry for the Telegram buttons."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ServiceMeta:
    key: str
    label: str
    description: str
    url_hints: list[str]

    def asdict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
        }


_SERVICES = [
    ServiceMeta("spotify", "🎵 Spotify Premium", "خدمة Spotify", ["spotify"]),
    ServiceMeta("youtube", "🎬 YouTube Premium", "خدمة YouTube", ["youtube", "google"]),
    ServiceMeta("google_one", "🤖 Google One / Gemini", "خدمة Google One / Gemini", ["googleone", "gemini", "google-one"]),
    ServiceMeta("boltnew", "👨‍🏫 Bolt.new", "خدمة Bolt.new", ["bolt"]),
    ServiceMeta("k12", "🏫 K12 ChatGPT Plus", "خدمة K12", ["openai", "chatgpt", "k12"]),
    ServiceMeta("veterans", "🎖️ Veterans", "خدمة Veterans", ["veteran", "military"]),
    ServiceMeta("perplexity", "🔍 Perplexity Pro", "خدمة Perplexity", ["perplexity"]),
]

SERVICE_REGISTRY: Dict[str, dict] = {s.key: s.asdict() for s in _SERVICES}
_BY_KEY = {s.key: s for s in _SERVICES}
SHEERID_URL_RE = re.compile(r"https?://[^\s]*sheerid[^\s]*", re.IGNORECASE)


def detect_service_from_url(url: str) -> Optional[str]:
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
