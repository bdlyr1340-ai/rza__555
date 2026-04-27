"""أوامر الأدمن."""
from __future__ import annotations

import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.db import models

log = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    await update.message.reply_markdown(
        "🛠 *لوحة الأدمن*\n\n"
        "/stats — إحصائيات\n"
        "/addcredit `<user_id> <amount>` — إضافة رصيد\n"
        "/ban `<user_id>` — حظر مستخدم\n"
        "/unban `<user_id>` — رفع الحظر\n"
        "/broadcast `<message>` — رسالة لكل المستخدمين"
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    s = await models.admin_stats()
    rate = (s["ver_success"] / s["ver_total"] * 100) if s["ver_total"] else 0
    lines = [
        "📊 *الإحصائيات*",
        f"المستخدمون: *{s['users_total']}* (اليوم: {s['users_today']})",
        f"عمليات التحقق: *{s['ver_total']}* (اليوم: {s['ver_today']})",
        f"نسبة النجاح الكلية: *{rate:.1f}%*",
        "",
        "*حسب الخدمة:*",
    ]
    for r in s["per_service"]:
        n = int(r["n"]); ok = int(r["ok"])
        pct = (ok / n * 100) if n else 0
        lines.append(f"• `{r['service']}`: {ok}/{n} ({pct:.0f}%)")
    await update.message.reply_markdown("\n".join(lines))


async def cmd_addcredit(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = ctx.args or []
    if len(args) != 2 or not args[0].lstrip("-").isdigit() or not args[1].lstrip("-").isdigit():
        await update.message.reply_text("الاستخدام: /addcredit <user_id> <amount>")
        return
    user_id, amount = int(args[0]), int(args[1])
    if not await models.get_user(user_id):
        await update.message.reply_text("المستخدم غير موجود.")
        return
    new_credits = await models.add_credits(user_id, amount)
    await update.message.reply_text(f"✅ تم. رصيد المستخدم {user_id} = {new_credits}")


async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = ctx.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("الاستخدام: /ban <user_id>")
        return
    await models.set_banned(int(args[0]), True)
    await update.message.reply_text("🚫 تم الحظر.")


async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = ctx.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("الاستخدام: /unban <user_id>")
        return
    await models.set_banned(int(args[0]), False)
    await update.message.reply_text("✅ تم رفع الحظر.")


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    text = " ".join(ctx.args or []).strip()
    if not text:
        await update.message.reply_text("الاستخدام: /broadcast <رسالة>")
        return

    user_ids = await models.all_user_ids()
    await update.message.reply_text(f"📣 جاري الإرسال إلى {len(user_ids)} مستخدم…")
    sent = failed = 0
    for uid in user_ids:
        try:
            await ctx.bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # ~20 رسالة/ثانية
    await update.message.reply_text(f"✅ انتهى. أُرسلت: {sent} | فشلت: {failed}")
