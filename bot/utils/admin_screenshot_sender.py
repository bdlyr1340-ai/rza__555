"""Helper اختياري لإرسال لقطة للأدمن.

هذا الملف لا يشتغل وحده، فقط إذا أردت تستخدمه مستقبلاً.
التصحيح الأساسي يتم عبر tools/apply_counter_screenshot_patch.py
"""
from __future__ import annotations

import os
from typing import Any


async def send_admin_screenshot(ctx: Any, admin_id: int, screenshot_path: str, ver_id: int | str, success: bool = False) -> bool:
    """Send screenshot to admin if path exists. Returns True if sent."""
    if not screenshot_path or not os.path.exists(screenshot_path):
        return False

    caption = f"📸 لقطة {'نجاح' if success else 'خطأ'} للطلب #{ver_id}"
    with open(screenshot_path, "rb") as f:
        await ctx.bot.send_photo(admin_id, photo=f, caption=caption)
    return True
