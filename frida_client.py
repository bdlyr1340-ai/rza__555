import aiohttp
import asyncio
from config import FRIDA_AGENTS

async def run_frida_script(device_id: str, user_id: int, script_path: str = "hook_1m.js") -> str:
    agent_url = FRIDA_AGENTS.get(device_id)
    if not agent_url:
        return f"❌ الجهاز '{device_id}' غير مسجل في FRIDA_AGENTS"

    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {"script": script_path, "user_id": user_id}
            async with session.post(f"{agent_url}/run_frida", json=payload) as resp:
                if resp.status == 200:
                    result_text = await resp.text()
                    return f"✅ تم التنفيذ على {device_id}:\n{result_text[:500]}"
                else:
                    return f"⚠️ خطأ {resp.status} من الجهاز: {await resp.text()}"
    except asyncio.TimeoutError:
        return "⏰ انتهى الوقت – الجهاز لم يستجب خلال 60 ثانية"
    except Exception as e:
        return f"🔌 فشل الاتصال: {str(e)}"