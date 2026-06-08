"""
config.py — الإعدادات المركزية لبوت أذاني

.env variable names (exact match):
    TELEGRAM_TOKEN      — توكن البوت
    WEBHOOK_URL         — رابط الويب هوك
    PORT                — المنفذ (default: 8000)
    ADMIN_ID            — معرّف المالك
    WEBHOOK_SECRET      — سر الويب هوك
    ALLOWED_COUNTRIES   — أكواد الدول (فارغ = جميع الدول)
"""
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ───────────────────────────────────────────────────────────────────
TOKEN: str        = os.getenv("TELEGRAM_TOKEN", "")
WEBHOOK_URL: str  = os.getenv("WEBHOOK_URL", "")
PORT: int         = int(os.getenv("PORT", 8000))
_env_secret       = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_SECRET: str = _env_secret if _env_secret else secrets.token_hex(32)

# ── Admin ──────────────────────────────────────────────────────────────────────
OWNER_ID: int = int(os.getenv("ADMIN_ID", "0"))

# ── Countries (ISO 3166-1 alpha-2) ────────────────────────────────────────────
# ALLOWED_COUNTRIES="" in .env  →  all countries allowed (no restriction)
# ALLOWED_COUNTRIES=SA          →  Saudi Arabia only
# ALLOWED_COUNTRIES=SA,KW,AE   →  Gulf countries
_raw = os.getenv("ALLOWED_COUNTRIES", "")
ALLOWED_COUNTRIES: list[str] = [c.strip().upper() for c in _raw.split(",") if c.strip()]

# ── AlAdhan API ────────────────────────────────────────────────────────────────
ALADHAN_API_URL: str = os.getenv("ALADHAN_API_URL", "https://api.aladhan.com/v1/timings")
API_TIMEOUT: float   = 8.0
MAX_RETRIES: int     = 3

# ── Telegram Rate-Limit Budgets ────────────────────────────────────────────────
#
# Telegram documented hard limits:
#   • 30 messages/second  — global across ALL chats
#   • 1  message/second   — per individual private chat
#   • 20 messages/minute  — per group/channel
#
# Strategy:
#   • We target ≤ 25 msg/sec globally to stay safely under the 30/s cap.
#   • Every send is separated by TG_SEND_DELAY (≈ 0.04 s → 25 msg/s).
#   • On RetryAfter (429), we sleep the exact duration Telegram asks for,
#     then retry up to TG_RETRY_MAX times before giving up on that message.
#   • Broadcasts are chunked: BROADCAST_CHUNK messages, then a 1-second pause,
#     giving a sustained rate of ≈ 25 msg/s with periodic breathing room.
#   • Reminders are sequential within each user-check (not concurrent burst),
#     with TG_SEND_DELAY between each actual send call.

TG_SEND_DELAY: float    = 0.04    # seconds between sends  (= 25 msg/sec ceiling)
TG_RETRY_MAX: int       = 3       # max retries on 429 RetryAfter
TG_RETRY_BASE: float    = 1.0     # base sleep on non-RetryAfter errors (exponential)


# Reminder engine
REMINDER_BATCH_SIZE: int      = int(os.getenv("REMINDER_BATCH_SIZE", 50))
REMINDER_CHECK_INTERVAL: int  = 60   # seconds between full reminder scans

# ── Prayer calculation methods ────────────────────────────────────────────────
CALCULATION_METHODS: dict[int, dict[str, str]] = {
    1:  {"ar": "رابطة العالم الإسلامي",           "en": "Muslim World League (MWL)"},
    2:  {"ar": "أمريكا الشمالية (ISNA)",           "en": "North America (ISNA)"},
    3:  {"ar": "الهيئة المصرية للمساحة",           "en": "Egyptian General Survey Authority"},
    4:  {"ar": "أم القرى — مكة المكرمة",           "en": "Umm Al-Qura (Makkah)"},
    5:  {"ar": "جامعة العلوم الإسلامية — كراتشي", "en": "Karachi University of Islamic Sciences"},
    7:  {"ar": "مجلس أمريكا الشمالية للفقه",      "en": "ISNA (Fiqh Council)"},
    8:  {"ar": "منطقة الخليج العربي",              "en": "Gulf Region"},
    9:  {"ar": "الكويت",                            "en": "Kuwait"},
    10: {"ar": "قطر",                               "en": "Qatar"},
    11: {"ar": "سنغافورة",                          "en": "Singapore"},
    12: {"ar": "تركيا",                             "en": "Turkey"},
    13: {"ar": "طهران",                             "en": "Tehran"},
    14: {"ar": "الاتحاد الإسلامي لأمريكا الشمالية","en": "UIOF (France)"},
}

# ── Default method per country ────────────────────────────────────────────────
COUNTRY_DEFAULT_METHOD: dict[str, int] = {
    "SA": 4,   # أم القرى
    "KW": 9,   # الكويت
    "QA": 10,  # قطر
    "AE": 8,   # الخليج
    "BH": 8,
    "OM": 8,
    "EG": 3,
    "TR": 12,
    "IR": 13,
    "SG": 11,
    "PK": 5,
    "US": 2,
    "CA": 2,
}

# ── Prayer names & order ──────────────────────────────────────────────────────
PRAYER_ORDER: list[str] = ["Fajr", "Shuruq", "Dhuhr", "Asr", "Maghrib", "Isha"]

AR_PRAYER_NAMES: dict[str, str] = {
    "Fajr":    "الفجر",
    "Shuruq":  "الشروق",
    "Dhuhr":   "الظهر",
    "Asr":     "العصر",
    "Maghrib": "المغرب",
    "Isha":    "العشاء",
}

# ── Saudi cities preset ───────────────────────────────────────────────────────
# Format: name → (lat, lon, tz, country_iso)
SA_CITIES: dict[str, tuple] = {
    "مكة المكرمة":     (21.3891, 39.8579, "Asia/Riyadh", "SA"),
    "المدينة المنورة":  (24.5247, 39.5692, "Asia/Riyadh", "SA"),
    "الرياض":           (24.7136, 46.6753, "Asia/Riyadh", "SA"),
    "جدة":              (21.5433, 39.1728, "Asia/Riyadh", "SA"),
    "الدمام":           (26.4207, 50.0888, "Asia/Riyadh", "SA"),
    "الطائف":           (21.2703, 40.4158, "Asia/Riyadh", "SA"),
    "بريدة":            (26.3260, 43.9750, "Asia/Riyadh", "SA"),
    "تبوك":             (28.3998, 36.5716, "Asia/Riyadh", "SA"),
    "أبها":             (18.2164, 42.5053, "Asia/Riyadh", "SA"),
    "الأحساء":          (25.3796, 49.5878, "Asia/Riyadh", "SA"),
    "حائل":             (27.5219, 41.6907, "Asia/Riyadh", "SA"),
    "نجران":            (17.4924, 44.1277, "Asia/Riyadh", "SA"),
    "جيزان":            (16.8892, 42.5611, "Asia/Riyadh", "SA"),
}

# ── Conversation states ───────────────────────────────────────────────────────
(
    SELECTING_ACTION,
    TYPING_CUSTOM_CITY,
) = range(2)

# ── Storage ───────────────────────────────────────────────────────────────────
STORAGE_DIR: str = "storage"
GROUPS_FILE: str = "storage/groups.txt"
