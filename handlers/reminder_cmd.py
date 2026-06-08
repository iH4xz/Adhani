"""
handlers/reminder_cmd.py — /reminder أمر التحكم في التنبيهات
"""
from __future__ import annotations
import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.database import db
from utils.i18n import t

logger = logging.getLogger(__name__)


async def reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reminder — تبديل تفعيل/إيقاف التنبيهات"""
    user_id = update.effective_user.id
    settings = await db.get_user(user_id)
    lang = settings.get("language", "ar")

    if not settings.get("latitude"):
        await update.message.reply_text(t("set_city_first", lang))
        return

    current = bool(settings.get("reminder_enabled", 0))
    if current:
        await db.update_setting(user_id, "reminder_enabled", 0)
        await update.message.reply_text(t("reminder_off", lang))
    else:
        await db.update_setting(user_id, "reminder_enabled", 1)
        offset = settings.get("reminder_offset", 10)
        await update.message.reply_text(t("reminder_on", lang, offset=offset))
