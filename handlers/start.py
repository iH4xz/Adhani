"""
handlers/start.py — /start و اختيار المدينة
"""
from __future__ import annotations
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import SELECTING_ACTION, TYPING_CUSTOM_CITY, SA_CITIES, ALLOWED_COUNTRIES, COUNTRY_DEFAULT_METHOD
from services.database import db
from services.geo import geocode_city, get_preset, is_country_allowed, country_name
from handlers.keyboards import city_selection_kb
from utils.i18n import t
from utils.helpers import log_group_id

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    chat = update.effective_chat

    if chat and chat.type in ("group", "supergroup"):
        log_group_id(chat.id)

    settings = await db.get_user(user.id)
    lang = settings.get("language", "ar")
    city = settings.get("city") or ("مكة المكرمة" if lang == "ar" else "Makkah")

    text = t("welcome", lang, name=user.first_name, city=city)
    await update.message.reply_text(
        text,
        reply_markup=city_selection_kb(lang),
    )
    return SELECTING_ACTION


async def handle_preset_city(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              city_ar: str) -> int:
    """Handle a preset city button press."""
    query = update.callback_query
    user_id = query.from_user.id
    settings = await db.get_user(user_id)
    lang = settings.get("language", "ar")

    preset = get_preset(city_ar)
    if not preset:
        await query.edit_message_text(t("city_not_found", lang))
        return ConversationHandler.END

    lat, lon, tz, country_code = preset

    # Check if country is allowed
    if not is_country_allowed(country_code):
        await query.edit_message_text(t("country_not_allowed", lang))
        return ConversationHandler.END

    country = country_name(country_code, lang)
    default_method = COUNTRY_DEFAULT_METHOD.get(country_code, 4)

    await db.upsert_user(user_id, city_ar, country, lat, lon, tz)
    # Set default method for this country if user is new
    current_settings = await db.get_user(user_id)
    if not current_settings.get("latitude"):  # first time
        await db.update_setting(user_id, "method", default_method)

    await query.edit_message_text(
        t("city_saved", lang, city=city_ar, country=country, tz=tz),
    )
    return ConversationHandler.END


async def prompt_manual_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask user to type their city manually."""
    query = update.callback_query
    user_id = query.from_user.id
    settings = await db.get_user(user_id)
    lang = settings.get("language", "ar")
    await query.edit_message_text(t("type_city", lang))
    return TYPING_CUSTOM_CITY


async def handle_typed_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle a manually typed city name."""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    settings = await db.get_user(user_id)
    lang = settings.get("language", "ar")

    await update.message.reply_text(
        "⏳ " + ("جارٍ البحث..." if lang == "ar" else "Searching..."),
    )

    geo = await geocode_city(text)
    if not geo:
        await update.message.reply_text(t("city_not_found", lang))
        return TYPING_CUSTOM_CITY

    if not is_country_allowed(geo["country_code"]):
        await update.message.reply_text(t("country_not_allowed", lang))
        return TYPING_CUSTOM_CITY

    # Set default method for country
    default_method = COUNTRY_DEFAULT_METHOD.get(geo["country_code"], 4)

    await db.upsert_user(
        user_id,
        geo["city"],
        geo["country"],
        geo["lat"],
        geo["lon"],
        geo["timezone"],
    )
    await db.update_setting(user_id, "method", default_method)

    country_disp = country_name(geo["country_code"], lang)
    await update.message.reply_text(
        t("city_saved", lang,
          city=geo["city"],
          country=country_disp,
          tz=geo["timezone"]),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = await db.get_user(update.effective_user.id)
    lang = settings.get("language", "ar")
    await update.message.reply_text(t("cancelled", lang))
    return ConversationHandler.END
