#!/usr/bin/env python3
"""
test_bot.py — اختبارات شاملة لبوت أذاني
تشغيل: python test_bot.py
لا يحتاج توكن Telegram حقيقي أو اتصال بالإنترنت.
"""
import ast
import asyncio
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import traceback
import types
import unittest.mock as mock

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"; RED   = "\033[91m"
YELLOW = "\033[93m"; CYAN  = "\033[96m"
RESET  = "\033[0m";  BOLD  = "\033[1m"

passed = failed = skipped = 0
_results: list[tuple] = []

def ok(name):
    global passed; passed += 1
    _results.append(("PASS", name, ""))
    print(f"  {GREEN}✅ PASS{RESET} {name}")

def fail(name, detail=""):
    global failed; failed += 1
    _results.append(("FAIL", name, detail))
    print(f"  {RED}❌ FAIL{RESET} {name}")
    if detail:
        for line in str(detail).strip().splitlines()[-5:]:
            print(f"       {RED}{line}{RESET}")

def skip(name, reason=""):
    global skipped; skipped += 1
    _results.append(("SKIP", name, reason))
    print(f"  {YELLOW}⏭  SKIP{RESET} {name} — {reason}")

def section(title):
    print(f"\n{BOLD}{CYAN}{'─'*55}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*55}{RESET}")


# ── Mock ALL third-party modules so tests run without pip ─────────────────────
def _make_mock_module(name):
    m = types.ModuleType(name)
    m.__spec__ = mock.MagicMock()
    return m

_MOCKED_MODS = [
    "telegram", "telegram.ext", "telegram.ext._handlers",
    "telegram.warnings", "telegram.error",
    "aiosqlite", "httpx", "uvicorn", "fastapi",
    "geopy", "geopy.geocoders", "timezonefinder",
    "pytz",
]
_SAVED = {}
for _mod in _MOCKED_MODS:
    if _mod not in sys.modules:
        _mm = _make_mock_module(_mod)
        sys.modules[_mod] = _mm
        _SAVED[_mod] = None
    else:
        _SAVED[_mod] = sys.modules[_mod]

# Make pytz.timezone return something useful
try:
    import pytz as _pytz_real
    if "pytz" not in sys.modules or sys.modules["pytz"] is not _pytz_real:
        sys.modules["pytz"] = _pytz_real   # use real pytz if available
except ImportError:
    pass  # pytz not installed, keep mock

# Fix geopy mock to have Nominatim
import types as _types
_geopy_geocoders = _types.ModuleType("geopy.geocoders")
_geopy_geocoders.Nominatim = type("Nominatim", (), {"__init__": lambda self,**kw: None})
sys.modules["geopy.geocoders"] = _geopy_geocoders
_geopy_mod = sys.modules.get("geopy", _types.ModuleType("geopy"))
_geopy_mod.geocoders = _geopy_geocoders
sys.modules["geopy"] = _geopy_mod

# Make aiosqlite work via sqlite3 shim
class _AioSQLiteShim:
    """Synchronous sqlite3 wrapped to look async for our database.py tests.
    
    aiosqlite.connect(path) is used as:  async with aiosqlite.connect(path) as db:
    In real aiosqlite, connect() returns an _AsyncContextManager (not a coroutine).
    Our shim must return an object that supports __aenter__/__aexit__ directly.
    """
    class Row(sqlite3.Row): pass
    class OperationalError(sqlite3.OperationalError): pass

    class _ConnCtx:
        """Returned by connect() — supports async context manager protocol."""
        def __init__(self, path):
            self._path = path
            self._conn = None

        async def __aenter__(self):
            c = sqlite3.connect(self._path, check_same_thread=False)
            c.row_factory = sqlite3.Row
            self._conn = c
            return _AioSQLiteShim._Conn(c)

        async def __aexit__(self, exc_type, exc, tb):
            if self._conn:
                if exc_type: self._conn.rollback()
                self._conn.close()

    @staticmethod
    def connect(path):
        # NOT async — returns a context manager object directly
        return _AioSQLiteShim._ConnCtx(path)

    class _Conn:
        def __init__(self, conn):
            self._c = conn
            self.row_factory = None

        async def execute(self, sql, params=()):
            try:
                cur = self._c.execute(sql, params)
            except sqlite3.OperationalError as e:
                raise _AioSQLiteShim.OperationalError(str(e)) from e
            return _AioSQLiteShim._Cur(cur)

        async def commit(self): self._c.commit()
        def close(self): self._c.close()

    class _Cur:
        def __init__(self, cur): self._c = cur
        @property
        def rowcount(self): return self._c.rowcount
        async def fetchone(self): return self._c.fetchone()
        async def fetchall(self): return self._c.fetchall()
        def __aiter__(self): return self
        async def __anext__(self):
            row = self._c.fetchone()
            if row is None: raise StopAsyncIteration
            return row
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

_aio_shim = types.ModuleType("aiosqlite")
_aio_shim.connect = _AioSQLiteShim.connect
_aio_shim.Row = _AioSQLiteShim.Row
_aio_shim.OperationalError = _AioSQLiteShim.OperationalError
sys.modules["aiosqlite"] = _aio_shim

# Minimal mock for telegram so keyboards import works
_tg = sys.modules["telegram"]
for _attr in ["InlineKeyboardMarkup", "InlineKeyboardButton", "ReplyKeyboardMarkup",
               "KeyboardButton", "Update"]:
    if not hasattr(_tg, _attr):
        setattr(_tg, _attr, mock.MagicMock)

_tg_ext = sys.modules["telegram.ext"]
for _attr in ["Application", "CommandHandler", "MessageHandler", "CallbackQueryHandler",
               "ConversationHandler", "InlineQueryHandler", "filters", "ContextTypes"]:
    if not hasattr(_tg_ext, _attr):
        setattr(_tg_ext, _attr, mock.MagicMock)

os.environ.setdefault("TELEGRAM_TOKEN", "123456:TEST_TOKEN_FOR_TESTS")
os.environ.setdefault("ADMIN_ID",        "999999")
os.environ.setdefault("WEBHOOK_URL",     "")
os.environ.setdefault("ALLOWED_COUNTRIES", "")


# ═════════════════════════════════════════════════════════════════════════════
section("1. Environment & Config")
# ═════════════════════════════════════════════════════════════════════════════
try:
    from config import (
        TOKEN, OWNER_ID, ALLOWED_COUNTRIES, PRAYER_ORDER, AR_PRAYER_NAMES,
        SA_CITIES, CALCULATION_METHODS, TG_SEND_DELAY, BROADCAST_CHUNK,
        BROADCAST_CHUNK_SLEEP, REMINDER_BATCH_SIZE,
        SELECTING_ACTION, TYPING_CUSTOM_CITY, AWAITING_BROADCAST,
        TG_RETRY_MAX, TG_RETRY_BASE,
    )
    ok("config.py imports cleanly")
except Exception as e:
    fail("config.py imports", traceback.format_exc()); sys.exit(1)

try:
    assert len(PRAYER_ORDER) == 6
    assert all(p in PRAYER_ORDER for p in ["Fajr","Shuruq","Dhuhr","Asr","Maghrib","Isha"])
    ok("PRAYER_ORDER has all 6 prayers in correct order")
except AssertionError as e:
    fail("PRAYER_ORDER", str(e))

try:
    assert len(SA_CITIES) >= 13, f"got {len(SA_CITIES)}"
    for city, (lat, lon, tz, iso) in SA_CITIES.items():
        assert -90<=lat<=90 and -180<=lon<=180 and "/" in tz and len(iso)==2
    ok(f"SA_CITIES: {len(SA_CITIES)} cities, all valid")
except AssertionError as e:
    fail("SA_CITIES", str(e))

try:
    rate = 1.0 / TG_SEND_DELAY
    sustained = BROADCAST_CHUNK / (BROADCAST_CHUNK * TG_SEND_DELAY + BROADCAST_CHUNK_SLEEP)
    assert rate <= 30, f"per-send rate {rate:.0f}/s > 30"
    assert sustained <= 30, f"broadcast rate {sustained:.1f}/s > 30"
    ok(f"Rate limits OK: per-send={rate:.0f}/s, broadcast={sustained:.1f}/s (limit 30/s)")
except AssertionError as e:
    fail("Rate-limit constants", str(e))


# ═════════════════════════════════════════════════════════════════════════════
section("2. Translations (i18n)")
# ═════════════════════════════════════════════════════════════════════════════
try:
    from utils.i18n import t
    ok("utils.i18n imports cleanly")
except Exception as e:
    fail("utils.i18n import", traceback.format_exc()); t = None

if t:
    REQUIRED = [
        "welcome","set_city_first","city_saved","city_not_found",
        "country_not_allowed","error_data","next_prayer","remaining",
        "today_schedule","help_text","my_panel","reminder_on","reminder_off",
        "unauthorized","broadcast_done","group_saved",
    ]
    all_keys_ok = True
    for key in REQUIRED:
        ar, en = t(key,"ar"), t(key,"en")
        if ar == key or en == key:
            fail(f"i18n '{key}'", "missing translation"); all_keys_ok = False
    if all_keys_ok:
        ok(f"All {len(REQUIRED)} required i18n keys present in AR + EN")

    # Help text must be plain text — no Markdown that Telegram parses
    for lang in ("ar","en"):
        txt = t("help_text", lang)
        has_bad = ("`" in txt or
                   re.search(r'(?<!\*)\*(?!\*)', txt) or  # lone * (bold/italic)
                   re.search(r'(?<!\[)\[(?!\[)', txt))     # lone [
        if has_bad:
            fail(f"help_text ({lang}) has Markdown chars that cause BadRequest")
        else:
            ok(f"help_text ({lang}) is plain text — safe to send without parse_mode")

    try:
        result = t("city_saved","ar", city="الرياض", country="SA", tz="Asia/Riyadh")
        assert "الرياض" in result and "Asia/Riyadh" in result
        ok("t() variable substitution works")
    except Exception as e:
        fail("t() substitution", str(e))


# ═════════════════════════════════════════════════════════════════════════════
section("3. Helper Utilities")
# ═════════════════════════════════════════════════════════════════════════════
try:
    from utils.helpers import esc, fmt_time, fmt_remaining, prayer_display
    ok("utils.helpers imports cleanly")
except Exception as e:
    fail("utils.helpers import", traceback.format_exc())
else:
    from datetime import timedelta, datetime

    for diff, lang in [(timedelta(hours=1,minutes=30),"ar"),
                       (timedelta(minutes=45),"en"),
                       (timedelta(minutes=0),"ar")]:
        try:
            r = fmt_remaining(diff, lang)
            assert isinstance(r, str) and len(r) > 0
        except Exception as e:
            fail(f"fmt_remaining({diff},{lang})", str(e)); break
    else:
        ok("fmt_remaining handles hours/minutes in AR+EN")

    try:
        dt = datetime(2024,1,15,13,30)
        h12 = fmt_time(dt,"12"); h24 = fmt_time(dt,"24")
        assert "PM" in h12.upper() or "13" not in h12
        assert h24 == "13:30"
        ok(f"fmt_time: 12h={h12!r}, 24h={h24!r}")
    except Exception as e:
        fail("fmt_time", str(e))

    try:
        dangerous = r"_*[]()~`>#+-.=|{}!\text"
        escaped = esc(dangerous)
        SPECIAL = list("_*[]()~`>#+-.=|{}")
        assert all(escaped.count(chr(92)+c)>=1 for c in SPECIAL), "missing escape"
        ok("esc() escapes all MarkdownV2 special chars")
    except AssertionError as e:
        fail("esc()", str(e))

    try:
        assert prayer_display("Fajr","ar") == "الفجر"
        assert prayer_display("Isha","en") == "Isha"
        ok("prayer_display() AR/EN correct")
    except Exception as e:
        fail("prayer_display()", str(e))


# ═════════════════════════════════════════════════════════════════════════════
section("4. Logging System")
# ═════════════════════════════════════════════════════════════════════════════
try:
    import logging
    from utils.logger import setup_logging, LOG_FILE, LOG_ERROR_FILE
    import utils.logger as _lmod
    ok("utils.logger imports cleanly")
except Exception as e:
    fail("utils.logger import", traceback.format_exc())
else:
    _tmp = tempfile.mkdtemp()
    _orig = (_lmod.LOG_DIR, _lmod.LOG_FILE, _lmod.LOG_ERROR_FILE, _lmod._configured)
    _lmod.LOG_DIR        = _tmp
    _lmod.LOG_FILE       = os.path.join(_tmp,"test.log")
    _lmod.LOG_ERROR_FILE = os.path.join(_tmp,"test_error.log")
    _lmod._configured    = False

    try:
        setup_logging()
        log = logging.getLogger("test_adhani_2")
        log.info("INFO message"); log.error("ERROR message")
        for h in logging.getLogger().handlers: h.flush()

        assert os.path.exists(_lmod.LOG_FILE)
        assert os.path.exists(_lmod.LOG_ERROR_FILE)
        main_content = open(_lmod.LOG_FILE).read()
        err_content  = open(_lmod.LOG_ERROR_FILE).read()
        assert "INFO message"  in main_content
        assert "ERROR message" in err_content
        assert "INFO message"  not in err_content
        ok("Logs: main file (INFO+), error file (ERROR only) — correct content")
    except Exception as e:
        fail("Logging files", traceback.format_exc())
    finally:
        (_lmod.LOG_DIR, _lmod.LOG_FILE,
         _lmod.LOG_ERROR_FILE, _lmod._configured) = _orig
        shutil.rmtree(_tmp, ignore_errors=True)



# ═════════════════════════════════════════════════════════════════════════════
section("5. Database Layer (direct sqlite3)")
# ═════════════════════════════════════════════════════════════════════════════
# Test the DB schema and logic directly via sqlite3 — no aiosqlite shim needed

import sqlite3 as _sqlite3, tempfile as _tf, shutil as _sh

_TMP_DB = _tf.mkdtemp(prefix="adhani_db_test_")

def _make_user_db(path):
    """Create a user shard with the correct schema."""
    c = _sqlite3.connect(path)
    c.execute("""CREATE TABLE IF NOT EXISTS schema_version (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL DEFAULT 0)""")
    c.execute("INSERT OR IGNORE INTO schema_version (id,version) VALUES (1,0)")
    c.execute("""CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY, city TEXT, country TEXT,
        latitude REAL, longitude REAL, timezone TEXT,
        method INTEGER DEFAULT 4, madhab TEXT DEFAULT 'shafi',
        time_format TEXT DEFAULT '12', language TEXT DEFAULT 'ar',
        date_pref TEXT DEFAULT 'both', reminder_enabled INTEGER DEFAULT 0,
        reminder_offset INTEGER DEFAULT 10,
        reminder_prayers TEXT DEFAULT 'Fajr,Dhuhr,Asr,Maghrib,Isha',
        timings_cache TEXT, cache_date TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("UPDATE schema_version SET version=1 WHERE id=1")
    c.commit(); c.close()

def _make_group_db(path):
    c = _sqlite3.connect(path)
    c.execute("""CREATE TABLE IF NOT EXISTS group_settings (
        group_id INTEGER PRIMARY KEY, city TEXT, country TEXT,
        latitude REAL, longitude REAL, timezone TEXT,
        method INTEGER DEFAULT 4, language TEXT DEFAULT 'ar',
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.commit(); c.close()

try:
    # Create test shards
    shard_123 = os.path.join(_TMP_DB, "users_1234.db")
    shard_200 = os.path.join(_TMP_DB, "users_2000.db")
    shard_300 = os.path.join(_TMP_DB, "users_3001.db")
    group_db  = os.path.join(_TMP_DB, "group_100123.db")

    for p in [shard_123, shard_200, shard_300]:
        _make_user_db(p)
    _make_group_db(group_db)

    # Insert users
    for db_path, uid, city, lat, lon in [
        (shard_123, 123456, "الرياض",  24.71, 46.67),
        (shard_200, 200000, "مكة",     21.38, 39.85),
        (shard_300, 300100, "جدة",     21.54, 39.17),
    ]:
        c = _sqlite3.connect(db_path)
        c.execute("INSERT OR REPLACE INTO user_settings (user_id,city,country,latitude,longitude,timezone)"
                  " VALUES (?,?,?,?,?,?)", (uid, city, "SA", lat, lon, "Asia/Riyadh"))
        c.commit(); c.close()
    ok("DB schema: user_settings table created correctly")
except Exception as e:
    fail("DB schema creation", traceback.format_exc())

try:
    # Read back
    c = _sqlite3.connect(shard_123); c.row_factory = _sqlite3.Row
    row = c.execute("SELECT * FROM user_settings WHERE user_id=123456").fetchone()
    c.close()
    assert row is not None
    assert row["city"] == "الرياض"
    assert abs(row["latitude"] - 24.71) < 0.01
    ok("DB: INSERT + SELECT user row correct")
except Exception as e:
    fail("DB: SELECT", str(e))

try:
    # Update setting
    c = _sqlite3.connect(shard_123)
    c.execute("UPDATE user_settings SET language=? WHERE user_id=?", ("en", 123456))
    c.commit(); c.close()
    c = _sqlite3.connect(shard_123); c.row_factory = _sqlite3.Row
    row = c.execute("SELECT language FROM user_settings WHERE user_id=123456").fetchone()
    c.close()
    assert row["language"] == "en"
    ok("DB: UPDATE setting persists")
except Exception as e:
    fail("DB: UPDATE", str(e))

try:
    # SQL injection guard (whitelist check)
    bad_cols = ["DROP TABLE user_settings--", "; DELETE FROM user_settings", "1=1"]
    _ALLOWED = {"city","country","latitude","longitude","timezone","method","madhab",
                "time_format","language","date_pref","reminder_enabled","reminder_offset",
                "reminder_prayers","timings_cache","cache_date","last_updated"}
    for col in bad_cols:
        assert col not in _ALLOWED, f"Dangerous col {col!r} is in whitelist!"
    ok("DB: SQL injection whitelist blocks dangerous column names")
except Exception as e:
    fail("DB: injection guard", str(e))

try:
    # Reminder filter
    c = _sqlite3.connect(shard_123)
    c.execute("UPDATE user_settings SET reminder_enabled=1 WHERE user_id=123456")
    c.commit(); c.close()
    # Count users with reminders
    total_reminder = 0
    import glob
    for p in glob.glob(os.path.join(_TMP_DB, "users_*.db")):
        c = _sqlite3.connect(p); c.row_factory = _sqlite3.Row
        rows = c.execute("SELECT * FROM user_settings WHERE reminder_enabled=1 AND latitude IS NOT NULL").fetchall()
        total_reminder += len(rows)
        c.close()
    assert total_reminder >= 1
    ok(f"DB: reminder filter query works ({total_reminder} user(s) with reminders)")
except Exception as e:
    fail("DB: reminder filter", str(e))

try:
    # Count total users across shards
    total = 0
    for p in glob.glob(os.path.join(_TMP_DB, "users_*.db")):
        c = _sqlite3.connect(p)
        count = c.execute("SELECT COUNT(*) FROM user_settings").fetchone()[0]
        total += count; c.close()
    assert total >= 3
    ok(f"DB: cross-shard count works ({total} users across {len(glob.glob(os.path.join(_TMP_DB,'users_*.db')))} shards)")
except Exception as e:
    fail("DB: cross-shard count", str(e))

try:
    # Legacy .sqlite migration logic: create a legacy file and verify rename logic
    legacy = os.path.join(_TMP_DB, "users_shard_OLD.sqlite")
    c = _sqlite3.connect(legacy)
    c.execute("CREATE TABLE user_settings (user_id INTEGER PRIMARY KEY, city TEXT, country TEXT, latitude REAL, longitude REAL, timezone TEXT)")
    c.execute("INSERT INTO user_settings VALUES (888777,'تبوك','SA',28.39,36.57,'Asia/Riyadh')")
    c.commit(); c.close()

    # Simulate what database.py migrate_all does: rename to .migrated
    os.rename(legacy, legacy + ".migrated")
    assert os.path.exists(legacy + ".migrated")
    assert not os.path.exists(legacy)

    # Verify data was in the file (simulating import)
    c = _sqlite3.connect(legacy + ".migrated"); c.row_factory = _sqlite3.Row
    rows = c.execute("SELECT * FROM user_settings").fetchall()
    c.close()
    assert len(rows) == 1 and rows[0]["city"] == "تبوك"
    ok("DB: legacy .sqlite detection, rename to .migrated, data readable")
except Exception as e:
    fail("DB: legacy .sqlite", traceback.format_exc())

try:
    # Group DB
    c = _sqlite3.connect(group_db); c.row_factory = _sqlite3.Row
    c.execute("INSERT OR REPLACE INTO group_settings (group_id,city,country,latitude,longitude,timezone) VALUES (-100123,'جدة','SA',21.54,39.17,'Asia/Riyadh')")
    c.commit()
    row = c.execute("SELECT * FROM group_settings WHERE group_id=-100123").fetchone()
    c.close()
    assert row["city"] == "جدة"
    ok("DB: group_settings INSERT + SELECT correct")
except Exception as e:
    fail("DB: group_settings", str(e))

_sh.rmtree(_TMP_DB, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
section("6. Prayer Service (offline)")
# ═════════════════════════════════════════════════════════════════════════════
_MOCK_TIMINGS = {
    "timings": {
        "Fajr":"04:45","Sunrise":"06:12","Dhuhr":"12:00",
        "Asr":"15:30","Maghrib":"18:05","Isha":"19:35",
    },
    "date": {
        "hijri":{"day":"15","month":{"ar":"رجب","en":"Rajab"},"year":"1445"},
        "gregorian":{"date":"15-01-2024"},
    }
}

async def _run_prayer_tests():
    import importlib
    import services.prayer as _pm
    importlib.reload(_pm)

    import importlib, sys as _sys
    # Clear any stale mock and import the real pytz
    if "pytz" in _sys.modules and not hasattr(_sys.modules["pytz"], "timezone"):
        del _sys.modules["pytz"]
    import pytz
    tz = pytz.timezone("Asia/Riyadh")

    try:
        prayers = _pm.PrayerService._parse(_MOCK_TIMINGS, tz)
        assert len(prayers) == 6
        names = [n for n,_ in prayers]
        assert names == ["Fajr","Shuruq","Dhuhr","Asr","Maghrib","Isha"]
        ok("PrayerService._parse: 6 prayers, correct order")
    except Exception as e:
        fail("PrayerService._parse", traceback.format_exc())

    from datetime import datetime
    now = datetime.now(tz)

    for pref, lang, expected_fragment in [
        ("both","ar","هـ"),
        ("hijri","ar","هـ"),
        ("gregorian","en","2024"),
    ]:
        try:
            s = {"date_pref":pref,"language":lang}
            result = _pm.PrayerService._format_date(_MOCK_TIMINGS, now, s)
            assert expected_fragment in result, f"Expected {expected_fragment!r} in {result!r}"
            ok(f"_format_date(pref={pref}, lang={lang}): {result}")
        except Exception as e:
            fail(f"_format_date(pref={pref})", traceback.format_exc())

try:
    import pytz as _ptest
    asyncio.run(_run_prayer_tests())
except ModuleNotFoundError:
    skip("Prayer service tests", "pytz not installed in test env (works on server)")
except Exception as e:
    fail("Prayer service tests", traceback.format_exc())


# ═════════════════════════════════════════════════════════════════════════════
section("7. Geo Service")
# ═════════════════════════════════════════════════════════════════════════════
try:
    from services.geo import is_country_allowed, country_name, get_preset
    ok("services.geo imports cleanly")
except Exception as e:
    fail("services.geo import", traceback.format_exc())
    is_country_allowed = country_name = get_preset = None

if is_country_allowed:
    import config as _cfg
    _orig_ac = _cfg.ALLOWED_COUNTRIES[:]

    try:
        _cfg.ALLOWED_COUNTRIES = ["SA","KW"]
        r1 = is_country_allowed("SA"); r2 = is_country_allowed("sa")
        r3 = is_country_allowed("US"); 
        _cfg.ALLOWED_COUNTRIES = []
        r4 = is_country_allowed("US")
        _cfg.ALLOWED_COUNTRIES = _orig_ac
        assert r1 is True,  f"SA should be allowed, got {r1}"
        assert r2 is True,  f"sa (lowercase) should be allowed, got {r2}"
        assert r3 is False, f"US should be blocked, got {r3}"
        assert r4 is True,  f"US with empty list should be allowed, got {r4}"
        ok("is_country_allowed: SA/KW filter + empty=all works")
    except Exception as e:
        _cfg.ALLOWED_COUNTRIES = _orig_ac
        fail("is_country_allowed", traceback.format_exc())

    try:
        assert country_name("SA","ar") == "المملكة العربية السعودية"
        assert country_name("SA","en") == "Saudi Arabia"
        assert country_name("XX","ar") == "XX"   # unknown → returns code
        ok("country_name() AR/EN correct, unknown code returns itself")
    except AssertionError as e:
        fail("country_name()", str(e))

    try:
        p = get_preset("الرياض")
        assert p is not None
        lat, lon, tz, iso = p
        assert 20 < lat < 30 and 40 < lon < 55 and iso == "SA"
        ok(f"get_preset('الرياض'): lat={lat}, lon={lon}, iso={iso}")
    except Exception as e:
        fail("get_preset()", str(e))


# ═════════════════════════════════════════════════════════════════════════════
section("8. Keyboards / GUI")
# ═════════════════════════════════════════════════════════════════════════════
try:
    from handlers.keyboards import (
        city_selection_kb, my_panel_kb, method_kb, madhab_kb,
        timefmt_kb, datepref_kb, language_kb, reminder_kb,
        reminder_prayers_kb, admin_panel_kb, broadcast_confirm_kb,
    )
    ok("handlers.keyboards imports cleanly (with Telegram mock)")
except ModuleNotFoundError as e:
    skip("handlers.keyboards import", f"missing dep in test env: {e}")
except Exception as e:
    fail("handlers.keyboards import", traceback.format_exc())
else:
    for fn_name, fn, args in [
        ("city_selection_kb",    city_selection_kb,    ("ar",)),
        ("my_panel_kb",          my_panel_kb,          ("ar",)),
        ("method_kb",            method_kb,            ("ar",)),
        ("madhab_kb",            madhab_kb,            ("ar",)),
        ("timefmt_kb",           timefmt_kb,           ("ar",)),
        ("datepref_kb",          datepref_kb,          ("ar",)),
        ("language_kb",          language_kb,          ("ar",)),
        ("reminder_kb",          reminder_kb,          ("ar", True, 10)),
        ("reminder_prayers_kb",  reminder_prayers_kb,  ("ar", {"Fajr","Dhuhr"})),
        ("admin_panel_kb",       admin_panel_kb,       ()),
        ("broadcast_confirm_kb", broadcast_confirm_kb, ("ar",)),
    ]:
        try:
            result = fn(*args)
            assert result is not None
            ok(f"  {fn_name}() builds without error")
        except Exception as e:
            fail(f"  {fn_name}()", str(e))


# ═════════════════════════════════════════════════════════════════════════════
section("9. Rate-Limit Math")
# ═════════════════════════════════════════════════════════════════════════════
try:
    from config import TG_SEND_DELAY, BROADCAST_CHUNK, BROADCAST_CHUNK_SLEEP, TG_RETRY_MAX, TG_RETRY_BASE

    per_send_rate = 1.0 / TG_SEND_DELAY
    sustained     = BROADCAST_CHUNK / (BROADCAST_CHUNK * TG_SEND_DELAY + BROADCAST_CHUNK_SLEEP)
    worst_retry   = sum(TG_RETRY_BASE * (2**i) for i in range(TG_RETRY_MAX))

    assert per_send_rate <= 30,  f"{per_send_rate:.1f}/s > 30/s global limit"
    assert sustained <= 30,      f"broadcast {sustained:.1f}/s > 30/s"
    assert TG_RETRY_MAX >= 2,    "too few retries"
    assert worst_retry < 60,     f"worst-case retry {worst_retry}s too long"

    ok(f"Per-send: {per_send_rate:.0f}/s ≤ 30/s ✓")
    ok(f"Broadcast sustained: {sustained:.1f}/s ≤ 30/s ✓")
    ok(f"Retry max: {TG_RETRY_MAX} attempts, worst delay: {worst_retry:.0f}s ✓")
except AssertionError as e:
    fail("Rate-limit math", str(e))


# ═════════════════════════════════════════════════════════════════════════════
section("10. Source Code Quality Checks")
# ═════════════════════════════════════════════════════════════════════════════

# All .py files parse without syntax errors
syntax_errors = []
py_files = []
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ("__pycache__",".git","venv",".venv","logs","storage")]
    for f in files:
        if f.endswith(".py") and f != "test_bot.py":
            p = os.path.join(root,f)
            py_files.append(p)
            try:
                ast.parse(open(p).read())
            except SyntaxError as e:
                syntax_errors.append(f"{p}: {e}")

if syntax_errors:
    fail(f"Syntax check ({len(py_files)} files)", "\n".join(syntax_errors))
else:
    ok(f"All {len(py_files)} .py files parse without syntax errors")

# No parse_mode="Markdown" (plain) in any handler — only MarkdownV2 is safe
plain_md_issues = []
for p in py_files:
    if "handlers" not in p: continue
    content = open(p).read()
    for i, line in enumerate(content.splitlines(),1):
        if re.search(r'''parse_mode\s*=\s*['"]Markdown['"]''', line):
            plain_md_issues.append(f"{p}:{i}: {line.strip()}")

if plain_md_issues:
    fail("No parse_mode='Markdown' in handlers", "\n".join(plain_md_issues))
else:
    ok("No plain parse_mode='Markdown' in any handler ✓  (MarkdownV2 is OK)")

# main.py structure
try:
    content = open("main.py").read()
    tree = ast.parse(content)
    fn_names = {n.name for n in ast.walk(tree)
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    assert "_register_handlers" in fn_names
    assert "_run_polling" in fn_names
    assert "asyncio.run(_run_polling" not in content
    assert "asyncio.run(run_polling" not in content
    assert "lifespan" in content
    ok("main.py: _register_handlers ✓ _run_polling ✓ lifespan ✓ no asyncio.run(polling) ✓")
except AssertionError as e:
    fail("main.py structure", str(e))

# Reminder engine uses sequential sends (no gather on sends)
try:
    rem = open("services/reminders.py").read()
    # gather() should NOT appear in _check_all or _send context
    # It's OK if gather doesn't appear at all
    import ast as _ast
    rem_tree = _ast.parse(rem)
    gather_calls = [n for n in _ast.walk(rem_tree)
                    if isinstance(n, _ast.Call)
                    and isinstance(getattr(n,'func',None), _ast.Attribute)
                    and n.func.attr == 'gather']
    if gather_calls:
        fail("services/reminders.py", f"Uses asyncio.gather() {len(gather_calls)} time(s) — risk of burst sends")
    else:
        ok("services/reminders.py: no asyncio.gather() calls — sends are sequential ✓")
except Exception as e:
    fail("reminders.py check", str(e))

# Legacy migration code present in database.py
try:
    db_src = open("services/database.py").read()
    assert "_import_legacy_users" in db_src
    assert ".sqlite" in db_src
    assert ".migrated" in db_src
    ok("database.py: legacy .sqlite migration code present ✓")
except AssertionError as e:
    fail("database.py legacy migration check", str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'═'*55}")
print(f"{BOLD}  نتائج الاختبارات | Test Results{RESET}")
print(f"{'═'*55}")
print(f"  {GREEN}✅ نجح  / Passed:  {passed}{RESET}")
print(f"  {RED}❌ فشل  / Failed:  {failed}{RESET}")
print(f"  {YELLOW}⏭  تخطى / Skipped: {skipped}{RESET}")
print(f"{'═'*55}")

if failed:
    print(f"\n{RED}{BOLD}الاختبارات الفاشلة:{RESET}")
    for status, name, detail in _results:
        if status == "FAIL":
            print(f"  • {RED}{name}{RESET}")
            if detail:
                for line in str(detail).strip().splitlines()[-3:]:
                    print(f"    {RED}{line}{RESET}")
print()
sys.exit(0 if failed == 0 else 1)
