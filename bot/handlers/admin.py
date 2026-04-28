"""أوامر الأدمن."""
from __future__ import annotations

import asyncio
import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot import config
from bot.db import models

log = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def _admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات", callback_data="adm:stats")],
        [
            InlineKeyboardButton("💳 البطاقات", callback_data="adm:cards"),
            InlineKeyboardButton("➕ إضافة بطاقة", callback_data="adm:addcard"),
        ],
        [
            InlineKeyboardButton("💰 إضافة رصيد", callback_data="adm:addcredit_prompt"),
            InlineKeyboardButton("🚫 حظر مستخدم", callback_data="adm:ban_prompt"),
        ],
        [InlineKeyboardButton("📣 بث رسالة", callback_data="adm:broadcast_prompt")],
    ])


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    cs = await models.cards_stats()
    await update.effective_message.reply_markdown(
        "🛠 *لوحة الأدمن*\n\n"
        f"💳 البطاقات: {cs['unused']} متاحة / {cs['total']} إجمالي\n\n"
        "*الأوامر:*\n"
        "/stats — إحصائيات\n"
        "/addcredit `<user_id> <amount>` — إضافة رصيد\n"
        "/ban `<user_id>` — حظر مستخدم\n"
        "/unban `<user_id>` — رفع الحظر\n"
        "/broadcast `<message>` — رسالة لكل المستخدمين\n"
        "/addcard — إضافة بطاقة ائتمان\n"
        "/cards — عرض البطاقات\n"
        "/delcard `<id>` — حذف بطاقة",
        reply_markup=_admin_panel_kb(),
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


# ───────── بطاقات الدفع ─────────

def _mask_card(number: str) -> str:
    clean = number.replace(" ", "").replace("-", "")
    if len(clean) >= 8:
        return clean[:4] + " •••• " + clean[-4:]
    return "•••• " + clean[-4:] if len(clean) >= 4 else clean


async def cmd_addcard(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    ctx.user_data["card_flow"] = "number"
    await update.effective_message.reply_markdown(
        "💳 *إضافة بطاقة ائتمان*\n\n"
        "*الخطوة 1/4:* أرسل رقم البطاقة (16 رقم):",
    )


async def cmd_cards(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    cards = await models.list_cards()
    if not cards:
        await update.effective_message.reply_text(
            "💳 لا توجد بطاقات محفوظة.\n\nاستخدم /addcard لإضافة بطاقة.",
        )
        return

    cs = await models.cards_stats()
    lines = [f"💳 *البطاقات* ({cs['unused']} متاحة / {cs['total']} إجمالي)\n"]
    for card in cards:
        status = "✅ متاحة" if not card["is_used"] else f"❌ مستخدمة (بواسطة {card.get('used_by', '—')})"
        lines.append(
            f"• `#{card['id']}` {_mask_card(card['card_number'])} — {card['card_holder']} — "
            f"{card['expiry_month']:02d}/{card['expiry_year']} — {status}"
        )
    lines.append("\nلحذف بطاقة: /delcard `<id>`")
    await update.effective_message.reply_markdown("\n".join(lines))


async def cmd_delcard(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = ctx.args or []
    if not args or not args[0].isdigit():
        await update.effective_message.reply_text("الاستخدام: /delcard <id>")
        return
    card_id = int(args[0])
    if await models.delete_card(card_id):
        await update.effective_message.reply_text(f"✅ تم حذف البطاقة #{card_id}")
    else:
        await update.effective_message.reply_text(f"❌ البطاقة #{card_id} غير موجودة.")


async def on_admin_card_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle admin card flow text input. Returns True if handled."""
    if not _is_admin(update.effective_user.id):
        return False
    card_step = ctx.user_data.get("card_flow")
    if not card_step:
        return False

    msg = update.effective_message
    text = msg.text.strip()

    if card_step == "number":
        clean = re.sub(r"[\s\-]", "", text)
        if not re.fullmatch(r"\d{13,19}", clean):
            await msg.reply_text("❌ رقم البطاقة غير صالح. أرسل 13-19 رقم:")
            return True
        ctx.user_data["card_number"] = clean
        ctx.user_data["card_flow"] = "holder"
        await msg.reply_markdown(
            f"✅ رقم البطاقة: `{_mask_card(clean)}`\n\n"
            "*الخطوة 2/4:* أرسل اسم صاحب البطاقة (كما هو مكتوب على البطاقة):"
        )
        try:
            await msg.delete()
        except Exception:
            pass
        return True

    if card_step == "holder":
        if len(text) < 2:
            await msg.reply_text("❌ الاسم قصير جداً. أرسل الاسم كاملاً:")
            return True
        ctx.user_data["card_holder"] = text.upper()
        ctx.user_data["card_flow"] = "expiry"
        await msg.reply_markdown(
            f"✅ الاسم: `{text.upper()}`\n\n"
            "*الخطوة 3/4:* أرسل تاريخ الانتهاء (مثال: `12/27` أو `03/2028`):"
        )
        return True

    if card_step == "expiry":
        m = re.fullmatch(r"(\d{1,2})\s*/\s*(\d{2,4})", text)
        if not m:
            await msg.reply_text("❌ صيغة غير صحيحة. أرسل مثل: 12/27 أو 03/2028")
            return True
        month = int(m.group(1))
        year = int(m.group(2))
        if year < 100:
            year += 2000
        if month < 1 or month > 12:
            await msg.reply_text("❌ الشهر يجب أن يكون بين 1 و 12.")
            return True
        ctx.user_data["card_expiry_month"] = month
        ctx.user_data["card_expiry_year"] = year
        ctx.user_data["card_flow"] = "cvv"
        await msg.reply_markdown(
            f"✅ تاريخ الانتهاء: `{month:02d}/{year}`\n\n"
            "*الخطوة 4/4:* أرسل رمز CVV (3 أو 4 أرقام خلف البطاقة):"
        )
        return True

    if card_step == "cvv":
        clean = text.strip()
        if not re.fullmatch(r"\d{3,4}", clean):
            await msg.reply_text("❌ CVV يجب أن يكون 3 أو 4 أرقام:")
            return True
        # Save the card
        card = await models.add_card(
            card_number=ctx.user_data.pop("card_number"),
            card_holder=ctx.user_data.pop("card_holder"),
            expiry_month=ctx.user_data.pop("card_expiry_month"),
            expiry_year=ctx.user_data.pop("card_expiry_year"),
            cvv=clean,
            added_by=update.effective_user.id,
        )
        ctx.user_data.pop("card_flow", None)
        try:
            await msg.delete()
        except Exception:
            pass

        cs = await models.cards_stats()
        await msg.reply_markdown(
            f"✅ *تم حفظ البطاقة #{card['id']}*\n\n"
            f"رقم: `{_mask_card(card['card_number'])}`\n"
            f"الاسم: `{card['card_holder']}`\n"
            f"الانتهاء: `{card['expiry_month']:02d}/{card['expiry_year']}`\n\n"
            f"💳 البطاقات المتاحة الآن: {cs['unused']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة بطاقة أخرى", callback_data="adm:addcard")],
                [InlineKeyboardButton("💳 عرض البطاقات", callback_data="adm:cards")],
                [InlineKeyboardButton("⬅️ تخطي", callback_data="adm:panel")],
            ]),
        )
        return True

    return False


async def on_admin_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle admin panel inline buttons. Returns True if handled."""
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("adm:"):
        return False
    if not _is_admin(query.from_user.id):
        await query.answer("⛔ غير مصرح")
        return True

    await query.answer()
    action = data.split(":", 1)[1]

    if action == "panel":
        cs = await models.cards_stats()
        await query.edit_message_text(
            f"🛠 *لوحة الأدمن*\n\n💳 البطاقات: {cs['unused']} متاحة / {cs['total']} إجمالي",
            parse_mode="Markdown",
            reply_markup=_admin_panel_kb(),
        )
        return True

    if action == "stats":
        s = await models.admin_stats()
        rate = (s["ver_success"] / s["ver_total"] * 100) if s["ver_total"] else 0
        lines = [
            "📊 *الإحصائيات*",
            f"المستخدمون: *{s['users_total']}* (اليوم: {s['users_today']})",
            f"الطلبات: *{s['ver_total']}* (اليوم: {s['ver_today']})",
            f"نسبة النجاح: *{rate:.1f}%*",
        ]
        for r in s["per_service"]:
            n, ok = int(r["n"]), int(r["ok"])
            pct = (ok / n * 100) if n else 0
            lines.append(f"• `{r['service']}`: {ok}/{n} ({pct:.0f}%)")
        await query.edit_message_text(
            "\n".join(lines), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="adm:panel")]]),
        )
        return True

    if action == "cards":
        cards = await models.list_cards()
        cs = await models.cards_stats()
        if not cards:
            await query.edit_message_text(
                "💳 لا توجد بطاقات محفوظة.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ إضافة بطاقة", callback_data="adm:addcard")],
                    [InlineKeyboardButton("⬅️ رجوع", callback_data="adm:panel")],
                ]),
            )
            return True
        lines = [f"💳 *البطاقات* ({cs['unused']} متاحة / {cs['total']} إجمالي)\n"]
        for card in cards:
            status = "✅" if not card["is_used"] else "❌"
            lines.append(
                f"{status} `#{card['id']}` {_mask_card(card['card_number'])} — {card['card_holder']} — "
                f"{card['expiry_month']:02d}/{card['expiry_year']}"
            )
        lines.append("\nلحذف: /delcard `<id>`")
        await query.edit_message_text(
            "\n".join(lines), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة بطاقة", callback_data="adm:addcard")],
                [InlineKeyboardButton("⬅️ رجوع", callback_data="adm:panel")],
            ]),
        )
        return True

    if action == "addcard":
        ctx.user_data["card_flow"] = "number"
        await query.edit_message_text(
            "💳 *إضافة بطاقة ائتمان*\n\n"
            "*الخطوة 1/4:* أرسل رقم البطاقة (16 رقم):",
            parse_mode="Markdown",
        )
        return True

    if action == "addcredit_prompt":
        await query.edit_message_text(
            "💰 أرسل الأمر:\n`/addcredit <user_id> <amount>`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="adm:panel")]]),
        )
        return True

    if action == "ban_prompt":
        await query.edit_message_text(
            "🚫 أرسل الأمر:\n`/ban <user_id>`\n\nلرفع الحظر: `/unban <user_id>`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="adm:panel")]]),
        )
        return True

    if action == "broadcast_prompt":
        await query.edit_message_text(
            "📣 أرسل الأمر:\n`/broadcast <الرسالة>`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="adm:panel")]]),
        )
        return True

    return False
