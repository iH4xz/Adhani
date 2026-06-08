"""
handlers/settings.py — /my إعدادات المستخدم والـ callbacks

قاعدة: جميع النصوص تُرسل بدون parse_mode (plain text).
الرموز والتنسيق فقط عبر Unicode — لا Markdown.
"""
from __future__ import annotations
import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import CALCULATION_METHODS, PRAYER_ORDER
from services.database import db
from handlers.keyboards import (
    my_panel_kb, method_kb, madhab_kb, timefmt_kb,
    datepref_kb, language_kb, reminder_kb, reminder_prayers_kb,
)
from utils.i18n import t

logger = logging.getLogger(__name__)


def _build_my_text(data: dict, lang: str) -> str:
    """بناء نص لوحة الإعدادات — plain text فقط."""
    method_id       = int(data.get("method", 4))
    madhab          = data.get("madhab", "shafi")
    time_fmt        = data.get("time_format", "12")
    date_pref       = data.get("date_pref", "both")
    reminder_enabled = bool(data.get("reminder_enabled", 0))
    reminder_offset  = data.get("reminder_offset", 10)

    method_name  = CALCULATION_METHODS.get(method_id, {}).get(lang, str(method_id))
    madhab_label = t("madhab_hanafi" if madhab == "hanafi" else "madhab_shafi", lang)
    date_label   = t(f"date_pref_{date_pref}", lang)
    lang_label   = t("lang_ar" if lang == "ar" else "lang_en", lang)
    r_status     = (t("reminder_status_on", lang, offset=reminder_offset)
                    if reminder_enabled else t("reminder_status_off", lang))

    return t("my_panel", lang,
             city=data.get("city", "—"),
             country=data.get("country", "—"),
             tz=data.get("timezone", "—"),
             method=method_name,
             madhab=madhab_label,
             time_fmt=time_fmt,
             date_pref=date_label,
             lang_label=lang_label,
             reminder_status=r_status)


async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/my — لوحة الإعدادات"""
    data = await db.get_user(update.effective_user.id)
    lang = data.get("language", "ar")
    await update.message.reply_text(
        _build_my_text(data, lang),
        reply_markup=my_panel_kb(lang),
        # NO parse_mode — plain text only
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await my_command(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — plain text, no parse_mode"""
    data = await db.get_user(update.effective_user.id)
    lang = data.get("language", "ar")
    await update.message.reply_text(t("help_text", lang))  # no parse_mode


# ── Callback router ────────────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts  = query.data.split("|")
    action = parts[0]
    user_id  = query.from_user.id
    settings = await db.get_user(user_id)
    lang     = settings.get("language", "ar")

    # ── city preset ───────────────────────────────────────────────────────────
    if action == "city":
        from handlers.start import handle_preset_city
        await handle_preset_city(update, context, parts[1])
        return

    # ── manual city ───────────────────────────────────────────────────────────
    if action == "manual_city":
        await query.edit_message_text(t("type_city", lang))
        return

    # ── /my change city ───────────────────────────────────────────────────────
    if action == "my" and len(parts) > 1 and parts[1] == "changecity":
        await query.edit_message_text(
            "🏙 " + ("استخدم /start لتغيير مدينتك" if lang == "ar"
                      else "Use /start to change your city")
        )
        return

    # ── menu navigation ───────────────────────────────────────────────────────
    if action == "menu":
        sub = parts[1] if len(parts) > 1 else ""

        if sub == "method":
            title = "🕌 " + ("اختر طريقة حساب المواقيت:" if lang == "ar"
                              else "Select prayer calculation method:")
            await query.edit_message_text(title, reply_markup=method_kb(lang))

        elif sub == "madhab":
            title = "📐 " + ("اختر مذهب حساب وقت العصر:" if lang == "ar"
                              else "Select Asr calculation madhab:")
            await query.edit_message_text(title, reply_markup=madhab_kb(lang))

        elif sub == "timefmt":
            title = "🕐 " + ("اختر تنسيق الوقت:" if lang == "ar"
                              else "Select time format:")
            await query.edit_message_text(title, reply_markup=timefmt_kb(lang))

        elif sub == "datepref":
            title = "📅 " + ("اختر تنسيق التاريخ:" if lang == "ar"
                              else "Select date format:")
            await query.edit_message_text(title, reply_markup=datepref_kb(lang))

        elif sub == "language":
            await query.edit_message_text(
                "🌐 اختر اللغة / Select language:",
                reply_markup=language_kb(lang),
            )

        elif sub == "reminder":
            r_enabled = bool(settings.get("reminder_enabled", 0))
            r_offset  = int(settings.get("reminder_offset", 10))
            r_prayers = settings.get("reminder_prayers", "Fajr,Dhuhr,Asr,Maghrib,Isha")
            status_txt = (
                ("✅ مفعّل" if lang == "ar" else "✅ Enabled") if r_enabled
                else ("❌ معطّل" if lang == "ar" else "❌ Disabled")
            )
            body = (
                f"🔔 {'إعدادات التنبيه' if lang == 'ar' else 'Reminder Settings'}\n\n"
                f"{'الحالة' if lang == 'ar' else 'Status'}: {status_txt}\n"
                f"{'قبل الصلاة بـ' if lang == 'ar' else 'Before prayer'}: "
                f"{r_offset} {'دقيقة' if lang == 'ar' else 'min'}\n"
                f"{'الصلوات' if lang == 'ar' else 'Prayers'}: {r_prayers}"
            )
            await query.edit_message_text(
                body, reply_markup=reminder_kb(lang, r_enabled, r_offset),
            )

        elif sub == "reminder_prayers":
            current = set(
                (settings.get("reminder_prayers") or "Fajr,Dhuhr,Asr,Maghrib,Isha").split(",")
            )
            title = ("اختر الصلوات التي تريد التنبيه لها:" if lang == "ar"
                     else "Select prayers for reminders:")
            await query.edit_message_text(
                title, reply_markup=reminder_prayers_kb(lang, current),
            )

        elif sub == "back":
            fresh = await db.get_user(user_id)
            lng   = fresh.get("language", "ar")
            await query.edit_message_text(
                _build_my_text(fresh, lng),
                reply_markup=my_panel_kb(lng),
                # no parse_mode
            )
        return

    # ── apply setting ─────────────────────────────────────────────────────────
    if action == "set":
        key   = parts[1] if len(parts) > 1 else ""
        value = parts[2] if len(parts) > 2 else ""
        if key in ("method", "madhab"):
            await db.update_setting(user_id, "timings_cache", None)
            await db.update_setting(user_id, "cache_date", None)
        await db.update_setting(user_id, key, value)
        fresh = await db.get_user(user_id)
        lng   = fresh.get("language", "ar")
        await query.edit_message_text(
            _build_my_text(fresh, lng),
            reply_markup=my_panel_kb(lng),
        )
        return

    # ── toggle individual prayer ──────────────────────────────────────────────
    if action == "toggle_prayer":
        prayer  = parts[1] if len(parts) > 1 else ""
        current = set(
            (settings.get("reminder_prayers") or "Fajr,Dhuhr,Asr,Maghrib,Isha").split(",")
        )
        if prayer in current:
            current.discard(prayer)
        else:
            current.add(prayer)
        if not current:
            current = {"Fajr"}
        new_val = ",".join(p for p in PRAYER_ORDER if p in current)
        await db.update_setting(user_id, "reminder_prayers", new_val)
        title = ("اختر الصلوات التي تريد التنبيه لها:" if lang == "ar"
                 else "Select prayers for reminders:")
        await query.edit_message_text(
            title, reply_markup=reminder_prayers_kb(lang, current),
        )
        return
