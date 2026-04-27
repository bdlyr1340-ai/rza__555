from __future__ import annotations

import asyncio
import logging
import os
import signal
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import asyncpg
from aiohttp import web
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import Conflict, InvalidToken, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ==========================================================
# RZA Telegram Bot - Railway Ready
# ملف واحد حتى ما تصير تعارضات بين db.py / package / imports
# ==========================================================


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def int_env(name: str, default: int) -> int:
    raw = env(name, str(default))
    try:
        return int(raw)
    except Exception:
        return default


def first_env(*names: str) -> str:
    for name in names:
        value = env(name)
        if value:
            return value
    return ""


def parse_admin_ids(raw: str) -> List[int]:
    ids: List[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    return ids


BOT_TOKEN = env("BOT_TOKEN")
DATABASE_URL = first_env(
    "DATABASE_URL",
    "POSTGRES_URL",
    "DATABASE_PRIVATE_URL",
    "POSTGRES_PRIVATE_URL",
    "DATABASE_PUBLIC_URL",
    "POSTGRES_PUBLIC_URL",
)
ADMIN_IDS = parse_admin_ids(env("ADMIN_IDS"))
DEFAULT_CREDITS = int_env("DEFAULT_CREDITS", 3)
REFERRAL_BONUS = int_env("REFERRAL_BONUS", 5)
PORT = int_env("PORT", 8080)
LOG_LEVEL = env("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
log = logging.getLogger("rza-bot")


MIGRATIONS = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    language TEXT NOT NULL DEFAULT 'ar',
    credits INTEGER NOT NULL DEFAULT 3,
    total_messages INTEGER NOT NULL DEFAULT 0,
    referred_by BIGINT,
    is_banned BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT NOT NULL,
    referred_id BIGINT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bot_logs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    event TEXT NOT NULL,
    data TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_bot_logs_created_at ON bot_logs(created_at DESC);
"""


@dataclass
class UserRow:
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    language: str = "ar"
    credits: int = DEFAULT_CREDITS
    total_messages: int = 0
    referred_by: Optional[int] = None
    is_banned: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserRow":
        return cls(
            user_id=int(data.get("user_id") or 0),
            username=data.get("username"),
            first_name=data.get("first_name"),
            language=data.get("language") or "ar",
            credits=int(data.get("credits") or 0),
            total_messages=int(data.get("total_messages") or 0),
            referred_by=data.get("referred_by"),
            is_banned=bool(data.get("is_banned")),
        )


class Store:
    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None
        self.memory_users: Dict[int, UserRow] = {}
        self.db_enabled = False

    async def connect(self) -> None:
        if not DATABASE_URL:
            log.warning("DATABASE_URL is missing. Bot will run with temporary memory storage.")
            return
        try:
            self.pool = await asyncio.wait_for(
                asyncpg.create_pool(
                    dsn=DATABASE_URL,
                    min_size=1,
                    max_size=5,
                    command_timeout=20,
                ),
                timeout=25,
            )
            async with self.pool.acquire() as conn:
                await conn.execute(MIGRATIONS)
            self.db_enabled = True
            log.info("Database connected and migrations executed successfully")
        except Exception as e:
            self.pool = None
            self.db_enabled = False
            log.exception("Database connection failed. Bot will still respond using memory storage: %s", e)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def upsert_user(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        referred_by: Optional[int] = None,
    ) -> UserRow:
        if not self.db_enabled or not self.pool:
            row = self.memory_users.get(user_id)
            if row:
                row.username = username
                row.first_name = first_name
                return row
            row = UserRow(
                user_id=user_id,
                username=username,
                first_name=first_name,
                referred_by=referred_by,
                credits=DEFAULT_CREDITS,
            )
            self.memory_users[user_id] = row
            if referred_by and referred_by != user_id and referred_by in self.memory_users:
                self.memory_users[referred_by].credits += REFERRAL_BONUS
            return row

        async with self.pool.acquire() as conn:
            old = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
            if old:
                new = await conn.fetchrow(
                    """
                    UPDATE users
                       SET username=$2, first_name=$3, last_seen_at=NOW()
                     WHERE user_id=$1
                 RETURNING *
                    """,
                    user_id,
                    username,
                    first_name,
                )
                return UserRow.from_dict(dict(new))

            new = await conn.fetchrow(
                """
                INSERT INTO users (user_id, username, first_name, credits, referred_by)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                user_id,
                username,
                first_name,
                DEFAULT_CREDITS,
                referred_by,
            )

            if referred_by and referred_by != user_id:
                inserted = await conn.fetchrow(
                    """
                    INSERT INTO referrals (referrer_id, referred_id)
                    VALUES ($1, $2)
                    ON CONFLICT (referred_id) DO NOTHING
                    RETURNING id
                    """,
                    referred_by,
                    user_id,
                )
                if inserted:
                    await conn.execute(
                        "UPDATE users SET credits = credits + $1 WHERE user_id=$2",
                        REFERRAL_BONUS,
                        referred_by,
                    )
            return UserRow.from_dict(dict(new))

    async def get_user(self, user_id: int) -> Optional[UserRow]:
        if not self.db_enabled or not self.pool:
            return self.memory_users.get(user_id)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
            return UserRow.from_dict(dict(row)) if row else None

    async def touch_message(self, user_id: int) -> None:
        if not self.db_enabled or not self.pool:
            row = self.memory_users.get(user_id)
            if row:
                row.total_messages += 1
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET total_messages = total_messages + 1, last_seen_at=NOW() WHERE user_id=$1",
                user_id,
            )

    async def set_language(self, user_id: int, language: str) -> None:
        if not self.db_enabled or not self.pool:
            row = self.memory_users.get(user_id)
            if row:
                row.language = language
            return
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE users SET language=$1 WHERE user_id=$2", language, user_id)

    async def add_credits(self, user_id: int, amount: int) -> Optional[int]:
        if not self.db_enabled or not self.pool:
            row = self.memory_users.get(user_id)
            if not row:
                return None
            row.credits += amount
            return row.credits
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE users SET credits = credits + $1 WHERE user_id=$2 RETURNING credits",
                amount,
                user_id,
            )
            return int(row["credits"]) if row else None

    async def set_banned(self, user_id: int, banned: bool) -> bool:
        if not self.db_enabled or not self.pool:
            row = self.memory_users.get(user_id)
            if not row:
                return False
            row.is_banned = banned
            return True
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE users SET is_banned=$1 WHERE user_id=$2 RETURNING user_id",
                banned,
                user_id,
            )
            return bool(row)

    async def stats(self) -> Dict[str, int]:
        if not self.db_enabled or not self.pool:
            users = list(self.memory_users.values())
            return {
                "users": len(users),
                "banned": sum(1 for u in users if u.is_banned),
                "messages": sum(u.total_messages for u in users),
                "referrals": sum(1 for u in users if u.referred_by),
                "database": 0,
            }
        async with self.pool.acquire() as conn:
            users = await conn.fetchval("SELECT COUNT(*) FROM users")
            banned = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_banned=TRUE")
            messages = await conn.fetchval("SELECT COALESCE(SUM(total_messages), 0) FROM users")
            referrals = await conn.fetchval("SELECT COUNT(*) FROM referrals")
            return {
                "users": int(users or 0),
                "banned": int(banned or 0),
                "messages": int(messages or 0),
                "referrals": int(referrals or 0),
                "database": 1,
            }

    async def active_user_ids(self) -> List[int]:
        if not self.db_enabled or not self.pool:
            return [uid for uid, row in self.memory_users.items() if not row.is_banned]
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users WHERE is_banned=FALSE")
            return [int(r["user_id"]) for r in rows]


store = Store()
web_runner: Optional[web.AppRunner] = None


def is_admin(user_id: Optional[int]) -> bool:
    return bool(user_id is not None and user_id in ADMIN_IDS)


def main_keyboard(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("👤 حسابي", callback_data="account"),
            InlineKeyboardButton("🎁 رابط الدعوة", callback_data="ref"),
        ],
        [
            InlineKeyboardButton("🌐 اللغة", callback_data="language"),
            InlineKeyboardButton("ℹ️ المساعدة", callback_data="help"),
        ],
        [InlineKeyboardButton("✅ فحص الاتصال", callback_data="ping")],
    ]
    if is_admin(user_id):
        rows.append([InlineKeyboardButton("⚙️ لوحة الأدمن", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("العربية 🇮🇶", callback_data="lang_ar"),
            InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"),
        ],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="home")],
    ])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="home")]])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="home")],
    ])


async def ensure_user(update: Update) -> Optional[UserRow]:
    user = update.effective_user
    if not user:
        return None

    referred_by: Optional[int] = None
    msg = update.effective_message
    if msg and msg.text and msg.text.startswith("/start"):
        parts = msg.text.split(maxsplit=1)
        if len(parts) == 2:
            arg = parts[1].strip()
            if arg.startswith("ref_") and arg[4:].isdigit():
                referred_by = int(arg[4:])

    return await store.upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        referred_by=referred_by,
    )


async def send_or_edit(update: Update, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None, parse_mode: Optional[str] = None) -> None:
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.effective_message:
            await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramError as e:
        log.warning("send_or_edit failed: %s", e)
        if update.effective_message:
            await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def home(update: Update) -> None:
    row = await ensure_user(update)
    user = update.effective_user
    if not row or not user:
        return
    if row.is_banned:
        await send_or_edit(update, "🚫 حسابك محظور من استخدام البوت.")
        return

    if row.language == "en":
        text = (
            "Hello! Bot is responding successfully ✅\n\n"
            f"Your ID: <code>{user.id}</code>\n"
            f"Credits: <b>{row.credits}</b>\n"
            f"Database: <b>{'Connected' if store.db_enabled else 'Memory mode'}</b>\n\n"
            "Use the buttons below."
        )
    else:
        text = (
            "هلا بيك حبيبي 🌟\n\n"
            "البوت شغال ويستجيب ✅\n"
            f"آيديك: <code>{user.id}</code>\n"
            f"رصيدك الحالي: <b>{row.credits}</b>\n"
            f"قاعدة البيانات: <b>{'متصلة' if store.db_enabled else 'وضع مؤقت'}</b>\n\n"
            "استخدم الأزرار بالأسفل."
        )
    await send_or_edit(update, text, reply_markup=main_keyboard(user.id), parse_mode=ParseMode.HTML)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.info("/start from user_id=%s username=%s", update.effective_user.id if update.effective_user else None, update.effective_user.username if update.effective_user else None)
    await home(update)


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update)
    await update.effective_message.reply_text("pong ✅ البوت يستجيب")


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        await update.effective_message.reply_text(f"ID: <code>{user.id}</code>", parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update)
    text = (
        "ℹ️ أوامر البوت:\n\n"
        "/start - تشغيل القائمة\n"
        "/ping - فحص الاستجابة\n"
        "/id - عرض الآيدي\n"
        "/me - حسابي\n"
        "/ref - رابط الدعوة\n"
        "/help - المساعدة\n\n"
        "أوامر الأدمن:\n"
        "/stats\n"
        "/addcredit USER_ID AMOUNT\n"
        "/ban USER_ID\n"
        "/unban USER_ID\n"
        "/broadcast الرسالة"
    )
    await update.effective_message.reply_text(text, reply_markup=back_keyboard())


async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = await ensure_user(update)
    if not row:
        return
    username = f"@{row.username}" if row.username else "بدون"
    text = (
        "👤 حسابك\n\n"
        f"ID: <code>{row.user_id}</code>\n"
        f"Username: <b>{username}</b>\n"
        f"Credits: <b>{row.credits}</b>\n"
        f"Language: <b>{row.language}</b>\n"
        f"Messages: <b>{row.total_messages}</b>"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard())


async def cmd_ref(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update)
    user = update.effective_user
    if not user:
        return
    bot_user = await context.bot.get_me()
    link = f"https://t.me/{bot_user.username}?start=ref_{user.id}"
    await update.effective_message.reply_text(
        "🎁 رابط دعوتك:\n"
        f"<code>{link}</code>\n\n"
        f"كل دعوة ناجحة تضيف لك {REFERRAL_BONUS} كريدت.",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard(),
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id if user else None):
        await update.effective_message.reply_text("ما عندك صلاحية.")
        return
    s = await store.stats()
    await update.effective_message.reply_text(
        "📊 الإحصائيات\n\n"
        f"المستخدمين: {s['users']}\n"
        f"المحظورين: {s['banned']}\n"
        f"الإحالات: {s['referrals']}\n"
        f"الرسائل: {s['messages']}\n"
        f"قاعدة البيانات: {'متصلة' if s['database'] else 'وضع مؤقت'}"
    )


async def cmd_addcredit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id if user else None):
        await update.effective_message.reply_text("ما عندك صلاحية.")
        return
    if len(context.args) != 2:
        await update.effective_message.reply_text("الاستخدام: /addcredit USER_ID AMOUNT")
        return
    try:
        target = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text("USER_ID و AMOUNT لازم أرقام.")
        return
    balance = await store.add_credits(target, amount)
    if balance is None:
        await update.effective_message.reply_text("المستخدم غير موجود.")
    else:
        await update.effective_message.reply_text(f"تم ✅ الرصيد الجديد: {balance}")


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id if user else None):
        await update.effective_message.reply_text("ما عندك صلاحية.")
        return
    if len(context.args) != 1:
        await update.effective_message.reply_text("الاستخدام: /ban USER_ID")
        return
    try:
        ok = await store.set_banned(int(context.args[0]), True)
    except ValueError:
        ok = False
    await update.effective_message.reply_text("تم الحظر ✅" if ok else "المستخدم غير موجود أو الآيدي خطأ.")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id if user else None):
        await update.effective_message.reply_text("ما عندك صلاحية.")
        return
    if len(context.args) != 1:
        await update.effective_message.reply_text("الاستخدام: /unban USER_ID")
        return
    try:
        ok = await store.set_banned(int(context.args[0]), False)
    except ValueError:
        ok = False
    await update.effective_message.reply_text("تم إلغاء الحظر ✅" if ok else "المستخدم غير موجود أو الآيدي خطأ.")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id if user else None):
        await update.effective_message.reply_text("ما عندك صلاحية.")
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("الاستخدام: /broadcast رسالتك")
        return
    ids = await store.active_user_ids()
    await update.effective_message.reply_text(f"جاري الإرسال إلى {len(ids)} مستخدم…")
    sent = 0
    failed = 0
    for uid in ids:
        try:
            await context.bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramError:
            failed += 1
    await update.effective_message.reply_text(f"تم ✅\nنجح: {sent}\nفشل: {failed}")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = await ensure_user(update)
    user = update.effective_user
    msg = update.effective_message
    if not row or not user or not msg:
        return
    if row.is_banned:
        await msg.reply_text("🚫 حسابك محظور.")
        return
    await store.touch_message(user.id)
    await msg.reply_text("وصلت رسالتك ✅\nاختار من الأزرار أو اكتب /help", reply_markup=main_keyboard(user.id))


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    await q.answer()
    row = await ensure_user(update)
    if not row:
        return
    data = q.data or "home"

    if data == "home":
        await home(update)
        return
    if data == "ping":
        await q.edit_message_text("pong ✅ البوت يستجيب", reply_markup=back_keyboard())
        return
    if data == "help":
        await q.edit_message_text(
            "ℹ️ المساعدة\n\n"
            "اكتب /start حتى تظهر القائمة.\n"
            "اكتب /ping حتى تفحص الاتصال.\n"
            "اكتب /id حتى تعرف آيديك.",
            reply_markup=back_keyboard(),
        )
        return
    if data == "language":
        await q.edit_message_text("اختار اللغة / Choose language:", reply_markup=lang_keyboard())
        return
    if data in {"lang_ar", "lang_en"}:
        lang = "ar" if data == "lang_ar" else "en"
        await store.set_language(q.from_user.id, lang)
        await q.edit_message_text("تم تغيير اللغة ✅", reply_markup=main_keyboard(q.from_user.id))
        return
    if data == "account":
        username = f"@{row.username}" if row.username else "بدون"
        await q.edit_message_text(
            "👤 حسابك\n\n"
            f"ID: <code>{row.user_id}</code>\n"
            f"Username: <b>{username}</b>\n"
            f"Credits: <b>{row.credits}</b>\n"
            f"Language: <b>{row.language}</b>\n"
            f"Messages: <b>{row.total_messages}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(),
        )
        return
    if data == "ref":
        bot_user = await context.bot.get_me()
        link = f"https://t.me/{bot_user.username}?start=ref_{q.from_user.id}"
        await q.edit_message_text(
            "🎁 رابط دعوتك:\n"
            f"<code>{link}</code>\n\n"
            f"كل دعوة ناجحة تضيف لك {REFERRAL_BONUS} كريدت.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(),
        )
        return
    if data == "admin":
        if not is_admin(q.from_user.id):
            await q.edit_message_text("ما عندك صلاحية.", reply_markup=back_keyboard())
            return
        await q.edit_message_text("⚙️ لوحة الأدمن", reply_markup=admin_keyboard())
        return
    if data == "admin_stats":
        if not is_admin(q.from_user.id):
            await q.edit_message_text("ما عندك صلاحية.", reply_markup=back_keyboard())
            return
        s = await store.stats()
        await q.edit_message_text(
            "📊 الإحصائيات\n\n"
            f"المستخدمين: <b>{s['users']}</b>\n"
            f"المحظورين: <b>{s['banned']}</b>\n"
            f"الإحالات: <b>{s['referrals']}</b>\n"
            f"الرسائل: <b>{s['messages']}</b>\n"
            f"قاعدة البيانات: <b>{'متصلة' if s['database'] else 'وضع مؤقت'}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_keyboard(),
        )
        return

    await q.edit_message_text("زر غير معروف. ارجع للقائمة.", reply_markup=back_keyboard())


async def on_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("الأمر غير معروف. جرّب /start أو /ping")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Telegram update error: %s", context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("صار خطأ مؤقت، جرّب /start مرة ثانية.")
    except Exception:
        pass


async def health(request: web.Request) -> web.Response:
    text = "RZA Bot is running ✅\n"
    text += f"database={'connected' if store.db_enabled else 'memory'}\n"
    return web.Response(text=text)


async def start_health_server() -> None:
    global web_runner
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    web_runner = web.AppRunner(app)
    await web_runner.setup()
    site = web.TCPSite(web_runner, "0.0.0.0", PORT)
    await site.start()
    log.info("Health server started on port %s", PORT)


async def stop_health_server() -> None:
    global web_runner
    if web_runner:
        await web_runner.cleanup()
        web_runner = None


async def post_init(app: Application) -> None:
    await start_health_server()
    await store.connect()

    # يمسح أي Webhook قديم بدون حذف رسائلك الحالية حتى لا يبلع /start
    await app.bot.delete_webhook(drop_pending_updates=False)

    me = await app.bot.get_me()
    log.info("Telegram bot connected: @%s id=%s", me.username, me.id)
    log.info("Polling is active. Send /start or /ping to @%s", me.username)


async def post_shutdown(app: Application) -> None:
    await stop_health_server()
    await store.close()
    log.info("Bot stopped")


def build_application() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing in Railway Variables")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(False)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("me", cmd_me))
    app.add_handler(CommandHandler("account", cmd_me))
    app.add_handler(CommandHandler("ref", cmd_ref))

    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("addcredit", cmd_addcredit))
    app.add_handler(CommandHandler("addcredits", cmd_addcredit))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.COMMAND, on_unknown_command))
    app.add_error_handler(on_error)
    return app


def main() -> None:
    app = build_application()
    log.info("Starting Telegram polling...")
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
            poll_interval=1.0,
            timeout=20,
            close_loop=True,
        )
    except Conflict:
        log.critical("Telegram Conflict: another copy of this bot is running with the same BOT_TOKEN. Stop old Railway services/deployments, then redeploy.")
        raise
    except InvalidToken:
        log.critical("BOT_TOKEN is invalid. Copy the token again from @BotFather.")
        raise


if __name__ == "__main__":
    main()
