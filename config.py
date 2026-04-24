import os
import json

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# FRIDA_AGENTS يجب أن تكون JSON string مثال: {"device1":"http://192.168.1.5:5000"}
FRIDA_AGENTS_RAW = os.getenv("FRIDA_AGENTS", "{}")
try:
    FRIDA_AGENTS = json.loads(FRIDA_AGENTS_RAW)
except:
    FRIDA_AGENTS = {}