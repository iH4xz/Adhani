"""
handlers/group.py — أوامر المجموعات /g
"""
from __future__ import annotations
import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from config import COUNTRY_DEFAULT_METHOD
from services.database import db
from services.geo import geocode_city, is_country_allowed, country_name
from utils.helpers import log_group_id
from utils.i18n import t

logger = logging.getLogger(__name__)


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id,
            update.effective_user.id,
        )
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def g_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/g <city> <country_code> — ضبط مدينة المجموعة"""
    chat = update.effective_chat
    user_id = update.effective_user.id
    from config import OWNER_ID
    settings = await db.get_user(user_id)
    lang = settings.get("language", "ar")

    if not chat or chat.type not in ("group", "supergroup"):
        await update.message.reply_text(t("groups_only", lang))
        return

    log_group_id(chat.id)

    if not (await is_admin(update, context) or user_id == OWNER_ID):
        await update.message.reply_text(t("admin_only", lang))
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(t("group_usage", lang))
        return

    # Sanitize inputs
    city_raw  = re.sub(r'[^\w\s\u0600-\u06FF\-]', '', args[0])[:60].strip()
    cc_raw    = re.sub(r'[^A-Za-z]', '', args[-1])[:2].upper()

    if not city_raw:
        await update.message.reply_text(t("city_not_found", lang))
        return

    if not is_country_allowed(cc_raw) and cc_raw:
        await update.message.reply_text(t("country_not_allowed", lang))
        return

    query = f"{city_raw}, {cc_raw}" if cc_raw else city_raw
    geo = await geocode_city(query)
    if not geo:
        await update.message.reply_text(t("city_not_found", lang))
        return

    if not is_country_allowed(geo["country_code"]):
        await update.message.reply_text(t("country_not_allowed", lang))
        return

    await db.upsert_group(
        chat.id,
        geo["city"],
        geo["country"],
        geo["lat"],
        geo["lon"],
        geo["timezone"],
    )
    country_disp = country_name(geo["country_code"], lang)
    await update.message.reply_text(
        t("group_saved", lang,
          city=geo["city"],
          country=country_disp,
          tz=geo["timezone"]),
    )
