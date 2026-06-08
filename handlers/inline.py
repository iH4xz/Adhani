"""
handlers/inline.py — الاستعلامات المضمّنة (Inline Mode)
"""
from __future__ import annotations
import logging

from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.ext import ContextTypes

from services.database import db
from services.prayer import PrayerService
from utils.helpers import esc
from utils.i18n import t

logger = logging.getLogger(__name__)


async def inline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query.strip().lower()
    user_id = update.inline_query.from_user.id
    results = []

    if any(kw in (update.inline_query.query + query)
           for kw in ("أذاني", "اذاني", "prayer", "adhani")):
        settings = await db.get_user(user_id)
        lang = settings.get("language", "ar")

        if not settings.get("latitude"):
            results.append(InlineQueryResultArticle(
                id="no_city",
                title="اضبط مدينتك أولاً | Set your city first",
                input_message_content=InputTextMessageContent(
                    "⚠️ " + t("set_city_first", lang)
                ),
            ))
        else:
            name, time_str, rem, date = await PrayerService.next_prayer(user_id, settings)
            msg = (
                f"📅 {esc(date)}\n"
                f"🕌 {esc(t('next_prayer', lang))}: *{esc(name)}*\n"
                f"⏰ {esc(time_str)}\n"
                f"⏳ {esc(t('remaining', lang))}: *{esc(rem)}*\n"
                f"📍 {esc(settings.get('city', ''))}"
            )
            results.append(InlineQueryResultArticle(
                id="prayer",
                title=f"{t('next_prayer', lang)}: {name}",
                description=f"{time_str} ({rem})",
                input_message_content=InputTextMessageContent(
                    msg, parse_mode="MarkdownV2"
                ),
            ))
    else:
        results.append(InlineQueryResultArticle(
            id="hint",
            title="اكتب: أذاني | Type: prayer",
            description="لمعرفة وقت الصلاة القادمة | Next prayer time",
            input_message_content=InputTextMessageContent(
                "اكتب أذاني أو prayer لمعرفة وقت الصلاة القادم"
            ),
        ))

    await update.inline_query.answer(results, cache_time=2)
