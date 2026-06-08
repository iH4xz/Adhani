"""
utils/i18n.py — نظام الترجمة الثنائي (عربي / إنجليزي)

قاعدة مهمة: لا تستخدم Markdown في نصوص الترجمة.
كل النصوص عادية (plain text) — أي تنسيق يُضاف في الكود عند الإرسال.
"""
from __future__ import annotations

_STRINGS: dict[str, dict[str, str]] = {
    # ── عام ────────────────────────────────────────────────────────────────────
    "welcome": {
        "ar": "مرحباً {name} 👋\n\nأنا أذاني — بوت أوقات الصلاة 🕌\n📍 مدينتك الحالية: {city}\n\nاختر مدينتك أو اكتبها يدوياً:",
        "en": "Welcome {name} 👋\n\nI'm Adhani — your prayer times bot 🕌\n📍 Current city: {city}\n\nSelect your city or type it manually:",
    },
    "set_city_first": {
        "ar": "⚠️ يرجى ضبط مدينتك أولاً عبر /start",
        "en": "⚠️ Please set your city first via /start",
    },
    "city_saved": {
        "ar": "✅ تم الحفظ: {city}\n🌍 الدولة: {country}\n🕰 المنطقة الزمنية: {tz}",
        "en": "✅ Saved: {city}\n🌍 Country: {country}\n🕰 Timezone: {tz}",
    },
    "city_not_found": {
        "ar": "❌ لم أجد المدينة، حاول مجدداً أو اكتب باللغة الإنجليزية.",
        "en": "❌ City not found. Try again or write in English.",
    },
    "country_not_allowed": {
        "ar": "❌ هذا البوت متاح فقط للدول المدعومة.\nتواصل مع المطوّر للمزيد.",
        "en": "❌ This bot is only available for supported countries.\nContact the developer for more info.",
    },
    "error_data": {
        "ar": "⚠️ تعذّر جلب البيانات، يرجى المحاولة لاحقاً.",
        "en": "⚠️ Could not retrieve data, please try again later.",
    },
    "cancelled": {
        "ar": "تم الإلغاء.",
        "en": "Cancelled.",
    },
    "settings_updated": {
        "ar": "✅ تم التحديث.",
        "en": "✅ Updated.",
    },
    # ── صلوات ──────────────────────────────────────────────────────────────────
    "next_prayer":    {"ar": "الصلاة القادمة", "en": "Next Prayer"},
    "remaining":      {"ar": "المتبقي",         "en": "Remaining"},
    "today_schedule": {"ar": "📅 جدول صلوات اليوم", "en": "📅 Today's Prayer Schedule"},
    "next_label":     {"ar": "⬆️ الصلاة القادمة",   "en": "⬆️ Next prayer"},
    # ── وقت ────────────────────────────────────────────────────────────────────
    "hour":    {"ar": "ساعة",   "en": "hour"},
    "hours":   {"ar": "ساعات",  "en": "hours"},
    "minute":  {"ar": "دقيقة",  "en": "minute"},
    "minutes": {"ar": "دقائق",  "en": "minutes"},
    "and":     {"ar": "و",      "en": "and"},
    # ── تذكير ──────────────────────────────────────────────────────────────────
    "reminder_on": {
        "ar": "🔔 تم تفعيل التنبيهات قبل {offset} دقيقة من كل صلاة.\nاستخدم /my لضبط الإعدادات.",
        "en": "🔔 Reminders enabled {offset} min before each prayer.\nUse /my to customize.",
    },
    "reminder_off": {
        "ar": "🔕 تم إيقاف التنبيهات.",
        "en": "🔕 Reminders disabled.",
    },
    # ── إعدادات /my ────────────────────────────────────────────────────────────
    "my_panel": {
        "ar": (
            "⚙️ إعداداتي\n\n"
            "🏙 المدينة: {city}\n"
            "🌍 الدولة: {country}\n"
            "🕰 المنطقة: {tz}\n\n"
            "🕌 طريقة الحساب: {method}\n"
            "📐 مذهب العصر: {madhab}\n"
            "🕐 تنسيق الوقت: {time_fmt} ساعة\n"
            "📅 تنسيق التاريخ: {date_pref}\n"
            "🌐 اللغة: {lang_label}\n"
            "🔔 التنبيهات: {reminder_status}"
        ),
        "en": (
            "⚙️ My Settings\n\n"
            "🏙 City: {city}\n"
            "🌍 Country: {country}\n"
            "🕰 Timezone: {tz}\n\n"
            "🕌 Calc Method: {method}\n"
            "📐 Asr Madhab: {madhab}\n"
            "🕐 Time Format: {time_fmt}-hour\n"
            "📅 Date Format: {date_pref}\n"
            "🌐 Language: {lang_label}\n"
            "🔔 Reminders: {reminder_status}"
        ),
    },
    "reminder_status_on":  {"ar": "✅ مفعّل ({offset} د)", "en": "✅ On ({offset} min)"},
    "reminder_status_off": {"ar": "❌ معطّل",               "en": "❌ Off"},
    "madhab_shafi":        {"ar": "شافعي",                  "en": "Shafi"},
    "madhab_hanafi":       {"ar": "حنفي",                   "en": "Hanafi"},
    "date_pref_hijri":     {"ar": "هجري فقط",               "en": "Hijri only"},
    "date_pref_gregorian": {"ar": "ميلادي فقط",              "en": "Gregorian only"},
    "date_pref_both":      {"ar": "كلاهما",                  "en": "Both"},
    "lang_ar":             {"ar": "العربية",                 "en": "Arabic"},
    "lang_en":             {"ar": "الإنجليزية",              "en": "English"},
    # ── مجموعة ─────────────────────────────────────────────────────────────────
    "groups_only": {
        "ar": "❌ هذا الأمر للمجموعات فقط.",
        "en": "❌ This command is for groups only.",
    },
    "admin_only": {
        "ar": "❌ فقط مشرفو المجموعة يستطيعون تغيير الإعدادات.",
        "en": "❌ Only group admins can change group settings.",
    },
    "group_usage": {
        "ar": "📌 الاستخدام:\n/g المدينة رمز_الدولة\nمثال: /g Riyadh SA",
        "en": "📌 Usage:\n/g city country_code\nExample: /g Riyadh SA",
    },
    "group_saved": {
        "ar": "✅ تم تحديث إعدادات المجموعة:\n🏙 {city} — {country}\n🕰 {tz}",
        "en": "✅ Group settings updated:\n🏙 {city} — {country}\n🕰 {tz}",
    },
    # ── مساعدة — plain text, NO markdown ──────────────────────────────────────
    "help_text": {
        "ar": (
            "📚 أوامر بوت أذاني\n\n"
            "اكتب أذاني أو prayer — الصلاة القادمة\n"
            "/a — الصلاة القادمة\n"
            "/schedule — جدول صلوات اليوم\n"
            "/reminder — تفعيل/إيقاف التنبيهات\n"
            "/my — إعداداتي الشخصية\n"
            "/settings — الإعدادات\n"
            "/start — تغيير المدينة\n"
            "/help — عرض المساعدة\n\n"
            "📌 للمجموعات:\n"
            "/g المدينة رمز_الدولة — ضبط مدينة المجموعة\n"
            "مثال: /g Riyadh SA"
        ),
        "en": (
            "📚 Adhani Bot Commands\n\n"
            "Type prayer or adhani — Next prayer\n"
            "/a — Next prayer\n"
            "/schedule — Today's full schedule\n"
            "/reminder — Toggle reminders\n"
            "/my — My personal settings\n"
            "/settings — Settings\n"
            "/start — Change city\n"
            "/help — Show help\n\n"
            "📌 For groups:\n"
            "/g city country_code — Set group city\n"
            "Example: /g Riyadh SA"
        ),
    },
    # ── أدمن ───────────────────────────────────────────────────────────────────
    "unauthorized": {
        "ar": "❌ غير مصرح.",
        "en": "❌ Unauthorized.",
    },
    # ── مدينة يدوية ────────────────────────────────────────────────────────────
    "type_city": {
        "ar": "✍️ اكتب اسم مدينتك:\nمثال: Riyadh أو الرياض",
        "en": "✍️ Type your city name:\nExample: Riyadh or Cairo",
    },
    "other_city_btn":  {"ar": "✏️ مدينة أخرى",     "en": "✏️ Other City"},
    "back_btn":        {"ar": "⬅️ رجوع",            "en": "⬅️ Back"},
    "change_city_btn": {"ar": "🏙 تغيير المدينة",    "en": "🏙 Change City"},
}


def t(key: str, lang: str = "ar", **kwargs) -> str:
    """ترجمة مفتاح مع دعم المتغيرات. تُرجع plain text دائماً."""
    text = _STRINGS.get(key, {}).get(lang) or _STRINGS.get(key, {}).get("ar") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text
