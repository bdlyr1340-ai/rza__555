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
    await update.effective_message.reply_markdown(
        "🛠 *لوحة الأدمن*\n\n"
        "/stats — إحصائيات\n"
        "/addcredit `<user_id> <amount>` — إضافة رصيد\n"
        "/ban `<user_id>` — حظر مستخدم\n"
        "/unban `<user_id>` — رفع الحظر\n"
        "/broadcast `<message>` — رسالة لكل المستخدمين\n\n"
        "💳 *إدارة البطاقات:*\n"
        "/addcard `<رقم> <MM/YY> <CVV> [اسم]` — إضافة بطاقة\n"
        "/cards — عرض كل البطاقات\n"
        "/delcard `<رقم>` — حذف بطاقة"
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    s = await models.admin_stats()
    rate = (s["ver_success"] / s["ver_total"] * 100) if s["ver_total"] else 0
    lines = [
        "📊 *الإحصائيات*",
        f"المستخدمون: *{s['users_total']}* (اليوم: {s['users_today']})",
        f"الطلبات: *{s['ver_total']}* (اليوم: {s['ver_today']})",
        f"نسبة النجاح الكلية: *{rate:.1f}%*",
        "",
        "*حسب الخدمة:*",
    ]
    for r in s["per_service"]:
        n = int(r["n"])
        ok = int(r["ok"])
        pct = (ok / n * 100) if n else 0
        lines.append(f"• `{r['service']}`: {ok}/{n} ({pct:.0f}%)")
    await update.effective_message.reply_markdown("\n".join(lines))


async def cmd_addcredit(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = ctx.args or []
    if len(args) != 2 or not args[0].lstrip("-").isdigit() or not args[1].lstrip("-").isdigit():
        await update.effective_message.reply_text("الاستخدام: /addcredit <user_id> <amount>")
        return
    user_id, amount = int(args[0]), int(args[1])
    if not await models.get_user(user_id):
        await update.effective_message.reply_text("المستخدم غير موجود.")
        return
    new_credits = await models.add_credits(user_id, amount)
    await update.effective_message.reply_text(f"✅ تم. رصيد المستخدم {user_id} = {new_credits}")


async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = ctx.args or []
    if not args or not args[0].isdigit():
        await update.effective_message.reply_text("الاستخدام: /ban <user_id>")
        return
    await models.set_banned(int(args[0]), True)
    await update.effective_message.reply_text("🚫 تم الحظر.")


async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = ctx.args or []
    if not args or not args[0].isdigit():
        await update.effective_message.reply_text("الاستخدام: /unban <user_id>")
        return
    await models.set_banned(int(args[0]), False)
    await update.effective_message.reply_text("✅ تم رفع الحظر.")


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    text = " ".join(ctx.args or []).strip()
    if not text:
        await update.effective_message.reply_text("الاستخدام: /broadcast <رسالة>")
        return

    user_ids = await models.all_user_ids()
    await update.effective_message.reply_text(f"📣 جاري الإرسال إلى {len(user_ids)} مستخدم…")
    sent = failed = 0
    for uid in user_ids:
        try:
            await ctx.bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await update.effective_message.reply_text(f"✅ انتهى. أُرسلت: {sent} | فشلت: {failed}")


# ---------------------------------------------------------------------------
# Payment card management
# ---------------------------------------------------------------------------

async def cmd_addcard(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = ctx.args or []
    if len(args) < 3:
        await update.effective_message.reply_text(
            "الاستخدام: /addcard <رقم_البطاقة> <MM/YY> <CVV> [اسم_صاحب_البطاقة]\n"
            "مثال: /addcard 4242424242424242 12/28 123 John Doe"
        )
        return
    card_number = args[0].replace("-", "").replace(" ", "")
    expiry = args[1]
    cvv = args[2]
    cardholder = " ".join(args[3:]) if len(args) > 3 else ""

    if not card_number.isdigit() or len(card_number) < 13:
        await update.effective_message.reply_text("❌ رقم البطاقة غير صحيح.")
        return
    if "/" not in expiry:
        await update.effective_message.reply_text("❌ صيغة التاريخ: MM/YY (مثل 12/28)")
        return

    card_id = await models.add_payment_card(card_number, expiry, cvv, cardholder, update.effective_user.id)
    masked = "*" * (len(card_number) - 4) + card_number[-4:]
    await update.effective_message.reply_text(
        f"✅ تم إضافة البطاقة #{card_id}\n"
        f"💳 {masked} | {expiry} | {cardholder or '-'}"
    )


async def cmd_cards(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    cards = await models.list_payment_cards()
    if not cards:
        await update.effective_message.reply_text("💳 لا توجد بطاقات محفوظة.\n\nأضف بطاقة: /addcard")
        return
    lines = ["💳 *البطاقات المحفوظة:*\n"]
    for c in cards:
        num = c["card_number"]
        masked = "*" * (len(num) - 4) + num[-4:]
        status = "✅" if c["is_active"] else "❌"
        lines.append(
            f"{status} #{c['id']} | `{masked}` | {c['expiry']} | "
            f"{c['cardholder'] or '-'} | فشل: {c['fail_count']}"
        )
    lines.append("\nحذف: /delcard <رقم>")
    await update.effective_message.reply_markdown("\n".join(lines))


async def cmd_delcard(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = ctx.args or []
    if not args or not args[0].isdigit():
        await update.effective_message.reply_text("الاستخدام: /delcard <رقم_البطاقة>")
        return
    card_id = int(args[0])
    if await models.delete_payment_card(card_id):
        await update.effective_message.reply_text(f"✅ تم حذف البطاقة #{card_id}")
    else:
        await update.effective_message.reply_text(f"❌ البطاقة #{card_id} غير موجودة.")
