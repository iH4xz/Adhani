"""
services/prayer.py — خدمة أوقات الصلاة مع تخزين مؤقت وإعادة المحاولة
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
import pytz

from config import ALADHAN_API_URL, API_TIMEOUT, MAX_RETRIES, PRAYER_ORDER, AR_PRAYER_NAMES
from services.database import db
from utils.helpers import fmt_time, fmt_remaining, prayer_display

logger = logging.getLogger(__name__)

_API_MAP = {
    "Fajr": "Fajr",
    "Sunrise": "Shuruq",
    "Dhuhr": "Dhuhr",
    "Asr": "Asr",
    "Maghrib": "Maghrib",
    "Isha": "Isha",
}


class PrayerService:

    # ── API Fetch with retry & fallback ──────────────────────────────────────
    @staticmethod
    async def _fetch_api(lat: float, lon: float, method: int,
                         madhab: str, date_str: str) -> Optional[dict]:
        school = 1 if madhab == "hanafi" else 0
        params = {
            "latitude": lat, "longitude": lon,
            "method": method, "school": school,
            "date": date_str,
        }
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                    resp = await client.get(ALADHAN_API_URL, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("code") == 200:
                            return data.get("data")
                    elif resp.status_code in (301, 302, 307, 308):
                        location = resp.headers.get("location", "")
                        logger.warning(f"[prayer] API redirect {resp.status_code} → {location}")
                        if location:
                            async with httpx.AsyncClient(
                                timeout=API_TIMEOUT, follow_redirects=True
                            ) as client2:
                                resp2 = await client2.get(ALADHAN_API_URL, params=params)
                                if resp2.status_code == 200:
                                    return resp2.json().get("data")
                    else:
                        logger.warning(f"[prayer] API returned {resp.status_code} on attempt {attempt}")
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning(f"[prayer] Attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES:
                import asyncio
                await asyncio.sleep(1.5 * attempt)
        return None

    # ── Cache management ──────────────────────────────────────────────────────
    @staticmethod
    async def _get_or_fetch(user_id: int, settings: dict) -> Optional[dict]:
        tz_name = settings.get("timezone", "Asia/Riyadh")
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone("Asia/Riyadh")

        today = datetime.now(tz).strftime("%Y-%m-%d")
        cached_json = settings.get("timings_cache")
        cached_date = settings.get("cache_date")

        if cached_json and cached_date == today:
            try:
                return json.loads(cached_json)
            except Exception:
                pass

        lat = settings.get("latitude")
        lon = settings.get("longitude")
        method = int(settings.get("method", 4))
        madhab = settings.get("madhab", "shafi")
        date_str = datetime.now(tz).strftime("%d-%m-%Y")

        data = await PrayerService._fetch_api(lat, lon, method, madhab, date_str)
        if data:
            await db.update_cache(user_id, json.dumps(data), today)
            # Also update in-memory settings dict so callers don't re-fetch
            settings["timings_cache"] = json.dumps(data)
            settings["cache_date"] = today
        return data

    # ── Parse timings ─────────────────────────────────────────────────────────
    @staticmethod
    def _parse(timings_data: dict, tz) -> list[tuple[str, datetime]]:
        now = datetime.now(tz)
        timings = timings_data.get("timings", {})
        result = []
        for api_key, name in _API_MAP.items():
            t_str = timings.get(api_key, "")
            if not t_str:
                continue
            t_str = t_str.split()[0]  # strip timezone suffix like "(+03)"
            try:
                naive = datetime.strptime(f"{now.date()} {t_str}", "%Y-%m-%d %H:%M")
                aware = tz.localize(naive)
                result.append((name, aware))
            except (ValueError, Exception) as e:
                logger.warning(f"[prayer] parse error for {name} '{t_str}': {e}")
        return result

    # ── Date formatting ───────────────────────────────────────────────────────
    @staticmethod
    def _format_date(data: dict, now: datetime, settings: dict) -> str:
        date_pref = settings.get("date_pref", "both")
        lang = settings.get("language", "ar")
        hijri = data.get("date", {}).get("hijri", {})
        greg  = data.get("date", {}).get("gregorian", {})

        hijri_str = ""
        greg_str = ""

        if hijri and hijri.get("day"):
            m = hijri.get("month", {}).get("ar" if lang == "ar" else "en", "")
            hijri_str = f"{hijri['day']} {m} {hijri['year']} هـ"

        if greg and greg.get("date"):
            try:
                g_dt = datetime.strptime(greg["date"], "%d-%m-%Y")
                greg_str = g_dt.strftime("%d %B %Y")
            except Exception:
                greg_str = now.strftime("%d %B %Y")
        elif greg:
            greg_str = now.strftime("%d %B %Y")

        if date_pref == "hijri":
            return hijri_str or now.strftime("%d %B %Y")
        if date_pref == "gregorian":
            return greg_str or now.strftime("%d %B %Y")
        # both
        parts = [p for p in [hijri_str, greg_str] if p]
        return " | ".join(parts) if parts else now.strftime("%d %B %Y")

    # ── Public API ────────────────────────────────────────────────────────────
    @staticmethod
    async def next_prayer(user_id: int, settings: dict) -> tuple[str, str, str, str]:
        """Returns (name, time, remaining, date_str) for the next prayer."""
        lang = settings.get("language", "ar")
        data = await PrayerService._get_or_fetch(user_id, settings)
        if not data:
            return "—", "—", "—", "—"

        tz_name = settings.get("timezone", "Asia/Riyadh")
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone("Asia/Riyadh")

        now = datetime.now(tz)
        prayers = PrayerService._parse(data, tz)
        time_fmt = settings.get("time_format", "12")

        next_p = next(((n, t) for n, t in prayers if t > now), None)
        if not next_p:
            # wrap to next day Fajr
            fajr_time = prayers[0][1] + timedelta(days=1) if prayers else now + timedelta(hours=2)
            next_p = ("Fajr", fajr_time)

        name_disp = prayer_display(next_p[0], lang)
        return (
            name_disp,
            fmt_time(next_p[1], time_fmt),
            fmt_remaining(next_p[1] - now, lang),
            PrayerService._format_date(data, now, settings),
        )

    @staticmethod
    async def full_schedule(user_id: int, settings: dict) -> Optional[list[tuple[str, str]]]:
        """Returns list of (display_name, time_str) for all prayers."""
        lang = settings.get("language", "ar")
        data = await PrayerService._get_or_fetch(user_id, settings)
        if not data:
            return None

        tz_name = settings.get("timezone", "Asia/Riyadh")
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone("Asia/Riyadh")

        prayers = PrayerService._parse(data, tz)
        time_fmt = settings.get("time_format", "12")
        return [(prayer_display(n, lang), fmt_time(t, time_fmt)) for n, t in prayers]

    @staticmethod
    async def upcoming(user_id: int, settings: dict) -> list[tuple[str, datetime]]:
        """Returns list of (name, datetime) for prayers that haven't passed yet."""
        data = await PrayerService._get_or_fetch(user_id, settings)
        if not data:
            return []
        tz_name = settings.get("timezone", "Asia/Riyadh")
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone("Asia/Riyadh")
        now = datetime.now(tz)
        return [(n, t) for n, t in PrayerService._parse(data, tz) if t > now]

    @staticmethod
    async def get_raw_data(user_id: int, settings: dict) -> Optional[dict]:
        return await PrayerService._get_or_fetch(user_id, settings)
