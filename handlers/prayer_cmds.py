"""
handlers/prayer_cmds.py — أوامر عرض أوقات الصلاة
"""
from __future__ import annotations
import logging
from datetime import datetime

import pytz
from telegram import Update
from telegram.ext import ContextTypes

from config import PRAYER_ORDER
from services.database import db
from services.prayer import PrayerService
from utils.helpers import esc, prayer_display, fmt_time
from utils.i18n import t

logger = logging.getLogger(__name__)


def _build_next_prayer_msg(name: str, time_str: str, rem: str,
                            date: str, city: str, lang: str) -> str:
    return (
        f"📅 {esc(date)}\n"
        f"🕌 {esc(t('next_prayer', lang))}: *{esc(name)}*\n"
        f"⏰ {esc(time_str)}\n"
        f"⏳ {esc(t('remaining', lang))}: *{esc(rem)}*\n"
        f"📍 {esc(city)}"
    )


async def a_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/a — الصلاة القادمة"""
    user_id = update.effective_user.id
    settings = await db.get_user(user_id)
    lang = settings.get("language", "ar")

    if not settings.get("latitude"):
        await update.message.reply_text(t("set_city_first", lang))
        return

    name, time_str, rem, date = await PrayerService.next_prayer(user_id, settings)
    msg = _build_next_prayer_msg(
        name, time_str, rem, date,
        settings.get("city", ""), lang
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/schedule — جدول اليوم"""
    user_id = update.effective_user.id
    settings = await db.get_user(user_id)
    lang = settings.get("language", "ar")

    if not settings.get("latitude"):
        await update.message.reply_text(t("set_city_first", lang))
        return

    schedule = await PrayerService.full_schedule(user_id, settings)
    if not schedule:
        await update.message.reply_text(t("error_data", lang))
        return

    tz_name = settings.get("timezone", "Asia/Riyadh")
    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.timezone("Asia/Riyadh")
    now = datetime.now(tz)

    raw_data = await PrayerService.get_raw_data(user_id, settings)
    date_str = PrayerService._format_date(raw_data, now, settings) if raw_data else now.strftime("%d %B %Y")

    # Find next prayer name (un-translated)
    from services.prayer import PrayerService as PS
    prayers_raw = PS._parse(raw_data, tz) if raw_data else []
    next_raw = next((n for n, pt in prayers_raw if pt > now), None)

    # Build schedule dict {display_name: time}
    schedule_dict = {n: ts for n, ts in schedule}

    city_esc = esc(settings.get("city", ""))
    date_esc = esc(date_str)
    header = (
        f"📅 {date_esc}\n🕌 *{esc(t('today_schedule', lang))}*\n📍 {city_esc}\n\n"
    )

    lines = []
    for raw_name in PRAYER_ORDER:
        disp_name = prayer_display(raw_name, lang)
        time_s = schedule_dict.get(disp_name, "—")
        marker = "◀️" if raw_name == next_raw else "   "
        lines.append(f"{marker} *{esc(disp_name)}* — {esc(time_s)}")

    footer = f"\n\n_{esc(t('next_label', lang))}_"
    await update.message.reply_text(
        header + "\n".join(lines) + footer,
        parse_mode="MarkdownV2",
    )


async def adhani_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger on keywords: أذاني / اذاني / prayer / adhani"""
    if not update.message or not update.message.text:
        return
    txt = update.message.text
    lower = txt.lower()
    if not any(k in txt for k in ("أذاني", "اذاني")) and \
       not any(k in lower for k in ("prayer", "adhani")):
        return

    user_id = update.effective_user.id
    settings = await db.get_user(user_id)
    lang = settings.get("language", "ar")

    # Try group fallback
    if not settings.get("latitude"):
        chat = update.effective_chat
        if chat and chat.type in ("group", "supergroup"):
            grp = await db.get_group(chat.id)
            if grp and grp.get("latitude"):
                settings = {**grp, "method": 4, "madhab": "shafi",
                            "time_format": "12", "language": "ar", "date_pref": "both",
                            "timings_cache": None, "cache_date": None}
            else:
                await update.message.reply_text(
                    "⚠️ " + ("اضبط مدينتك /start أو اطلب من المشرف ضبط المجموعة /g"
                              if lang == "ar" else
                              "Set your city /start or ask admin to set group city /g")
                )
                return
        else:
            await update.message.reply_text(t("set_city_first", lang))
            return

    name, time_str, rem, date = await PrayerService.next_prayer(user_id, settings)
    msg = _build_next_prayer_msg(
        name, time_str, rem, date,
        settings.get("city", ""), lang
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")
