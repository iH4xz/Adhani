"""
handlers/keyboards.py — بناة لوحات المفاتيح (GUI) لجميع القوائم
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import (
    SA_CITIES, CALCULATION_METHODS, PRAYER_ORDER, AR_PRAYER_NAMES,
    ALLOWED_COUNTRIES,
)
from utils.i18n import t
from utils.helpers import esc


# ── /start — اختيار المدينة ──────────────────────────────────────────────────
def city_selection_kb(lang: str = "ar") -> InlineKeyboardMarkup:
    rows = []
    cities = list(SA_CITIES.keys())
    for i in range(0, len(cities), 2):
        row = []
        for city in cities[i:i+2]:
            row.append(InlineKeyboardButton(city, callback_data=f"city|{city}"))
        rows.append(row)
    rows.append([
        InlineKeyboardButton(t("other_city_btn", lang), callback_data="manual_city")
    ])
    return InlineKeyboardMarkup(rows)


# ── /my — لوحة الإعدادات الرئيسية ───────────────────────────────────────────
def my_panel_kb(lang: str = "ar") -> InlineKeyboardMarkup:
    if lang == "ar":
        kb = [
            [InlineKeyboardButton("🏙 تغيير المدينة", callback_data="my|changecity")],
            [
                InlineKeyboardButton("🕌 طريقة الحساب",  callback_data="menu|method"),
                InlineKeyboardButton("📐 مذهب العصر",    callback_data="menu|madhab"),
            ],
            [
                InlineKeyboardButton("🕐 تنسيق الوقت",  callback_data="menu|timefmt"),
                InlineKeyboardButton("📅 تنسيق التاريخ", callback_data="menu|datepref"),
            ],
            [InlineKeyboardButton("🌐 اللغة / Language", callback_data="menu|language")],
            [InlineKeyboardButton("🔔 إعدادات التنبيه",  callback_data="menu|reminder")],
        ]
    else:
        kb = [
            [InlineKeyboardButton("🏙 Change City", callback_data="my|changecity")],
            [
                InlineKeyboardButton("🕌 Calc Method",  callback_data="menu|method"),
                InlineKeyboardButton("📐 Asr Madhab",   callback_data="menu|madhab"),
            ],
            [
                InlineKeyboardButton("🕐 Time Format",  callback_data="menu|timefmt"),
                InlineKeyboardButton("📅 Date Format",  callback_data="menu|datepref"),
            ],
            [InlineKeyboardButton("🌐 اللغة / Language", callback_data="menu|language")],
            [InlineKeyboardButton("🔔 Reminder Settings", callback_data="menu|reminder")],
        ]
    return InlineKeyboardMarkup(kb)


def _back_row(lang: str, target: str = "back") -> list:
    return [InlineKeyboardButton(t("back_btn", lang), callback_data=f"menu|{target}")]


# ── طريقة الحساب ──────────────────────────────────────────────────────────────
def method_kb(lang: str = "ar") -> InlineKeyboardMarkup:
    rows = []
    for mid, names in CALCULATION_METHODS.items():
        rows.append([InlineKeyboardButton(names[lang], callback_data=f"set|method|{mid}")])
    rows.append(_back_row(lang))
    return InlineKeyboardMarkup(rows)


# ── مذهب العصر ────────────────────────────────────────────────────────────────
def madhab_kb(lang: str = "ar") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'✅ ' if lang=='ar' else ''}شافعي / Shafi",
                callback_data="set|madhab|shafi"
            ),
            InlineKeyboardButton(
                f"{'✅ ' if lang=='ar' else ''}حنفي / Hanafi",
                callback_data="set|madhab|hanafi"
            ),
        ],
        _back_row(lang),
    ])


# ── تنسيق الوقت ───────────────────────────────────────────────────────────────
def timefmt_kb(lang: str = "ar") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🕐 12 (AM/PM)", callback_data="set|time_format|12"),
            InlineKeyboardButton("🕐 24",          callback_data="set|time_format|24"),
        ],
        _back_row(lang),
    ])


# ── تنسيق التاريخ ─────────────────────────────────────────────────────────────
def datepref_kb(lang: str = "ar") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🗓 " + t("date_pref_hijri", lang),
                callback_data="set|date_pref|hijri"
            ),
            InlineKeyboardButton(
                "📅 " + t("date_pref_gregorian", lang),
                callback_data="set|date_pref|gregorian"
            ),
            InlineKeyboardButton(
                "🗓📅 " + t("date_pref_both", lang),
                callback_data="set|date_pref|both"
            ),
        ],
        _back_row(lang),
    ])


# ── اللغة ─────────────────────────────────────────────────────────────────────
def language_kb(lang: str = "ar") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇸🇦 العربية",  callback_data="set|language|ar"),
            InlineKeyboardButton("🇬🇧 English",  callback_data="set|language|en"),
        ],
        _back_row(lang),
    ])


# ── إعدادات التنبيه ───────────────────────────────────────────────────────────
def reminder_kb(lang: str, reminder_enabled: bool, offset: int) -> InlineKeyboardMarkup:
    toggle_label = (
        ("🔕 إيقاف التنبيهات" if lang == "ar" else "🔕 Disable Reminders")
        if reminder_enabled else
        ("🔔 تفعيل التنبيهات" if lang == "ar" else "🔔 Enable Reminders")
    )
    new_state = 0 if reminder_enabled else 1
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data=f"set|reminder_enabled|{new_state}")],
        [
            InlineKeyboardButton("⏱ 5 " + ("د" if lang == "ar" else "min"),  callback_data="set|reminder_offset|5"),
            InlineKeyboardButton("⏱ 10 " + ("د" if lang == "ar" else "min"), callback_data="set|reminder_offset|10"),
            InlineKeyboardButton("⏱ 15 " + ("د" if lang == "ar" else "min"), callback_data="set|reminder_offset|15"),
            InlineKeyboardButton("⏱ 30 " + ("د" if lang == "ar" else "min"), callback_data="set|reminder_offset|30"),
        ],
        [InlineKeyboardButton(
            "🕌 " + ("الصلوات المُذكَّر بها" if lang == "ar" else "Reminder Prayers"),
            callback_data="menu|reminder_prayers"
        )],
        _back_row(lang),
    ])


# ── اختيار الصلوات للتنبيه ────────────────────────────────────────────────────
def reminder_prayers_kb(lang: str, current_prayers: set[str]) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for p in PRAYER_ORDER:
        tick = "✅" if p in current_prayers else "⬜"
        name = AR_PRAYER_NAMES[p] if lang == "ar" else p
        row.append(InlineKeyboardButton(f"{tick} {name}", callback_data=f"toggle_prayer|{p}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(_back_row(lang, "reminder"))
    return InlineKeyboardMarkup(rows)


# ── لوحة الأدمن ───────────────────────────────────────────────────────────────
def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 الإحصائيات",    callback_data="admin|stats"),
            InlineKeyboardButton("👥 المجموعات",     callback_data="admin|groups"),
        ],
        [
            InlineKeyboardButton("📢 إذاعة رسالة",   callback_data="admin|broadcast"),
            InlineKeyboardButton("🔄 مسح الكاش",     callback_data="admin|clearcache"),
        ],
        [
            InlineKeyboardButton("🌍 الدول المسموحة", callback_data="admin|countries"),
            InlineKeyboardButton("🔧 معلومات النظام", callback_data="admin|sysinfo"),
        ],
    ])


# ── تأكيد الإذاعة ────────────────────────────────────────────────────────────
def broadcast_confirm_kb(lang: str = "ar") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأكيد الإرسال" if lang == "ar" else "✅ Confirm Send",
                                 callback_data="admin|broadcast_confirm"),
            InlineKeyboardButton("❌ إلغاء" if lang == "ar" else "❌ Cancel",
                                 callback_data="admin|broadcast_cancel"),
        ]
    ])
