"""
services/geo.py — خدمة تحديد الموقع الجغرافي والتحقق من الدولة
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

# geopy and timezonefinder are imported lazily inside geocode_city()
# slugify imported lazily inside geocode_city()

import config as _config
from config import SA_CITIES

logger = logging.getLogger(__name__)

_geolocator = None  # created lazily on first use

def _get_geolocator():
    global _geolocator
    if _geolocator is None:
        from geopy.geocoders import Nominatim
        _geolocator = Nominatim(user_agent="adhani_bot_v5", timeout=8)
    return _geolocator
_tf = None  # created lazily on first use

def _get_tf():
    global _tf
    if _tf is None:
        from timezonefinder import TimezoneFinder
        _tf = TimezoneFinder()
    return _tf

# Country code → Arabic/English name mapping (ISO 3166-1 alpha-2)
COUNTRY_NAMES: dict[str, dict[str, str]] = {
    "SA": {"ar": "المملكة العربية السعودية", "en": "Saudi Arabia"},
    "KW": {"ar": "الكويت", "en": "Kuwait"},
    "AE": {"ar": "الإمارات العربية المتحدة", "en": "United Arab Emirates"},
    "QA": {"ar": "قطر", "en": "Qatar"},
    "BH": {"ar": "البحرين", "en": "Bahrain"},
    "OM": {"ar": "سلطنة عمان", "en": "Oman"},
    "EG": {"ar": "مصر", "en": "Egypt"},
    "JO": {"ar": "الأردن", "en": "Jordan"},
    "LB": {"ar": "لبنان", "en": "Lebanon"},
    "SY": {"ar": "سوريا", "en": "Syria"},
    "IQ": {"ar": "العراق", "en": "Iraq"},
    "YE": {"ar": "اليمن", "en": "Yemen"},
    "LY": {"ar": "ليبيا", "en": "Libya"},
    "TN": {"ar": "تونس", "en": "Tunisia"},
    "DZ": {"ar": "الجزائر", "en": "Algeria"},
    "MA": {"ar": "المغرب", "en": "Morocco"},
    "SD": {"ar": "السودان", "en": "Sudan"},
    "TR": {"ar": "تركيا", "en": "Turkey"},
    "PK": {"ar": "باكستان", "en": "Pakistan"},
    "IN": {"ar": "الهند", "en": "India"},
    "US": {"ar": "الولايات المتحدة", "en": "United States"},
    "GB": {"ar": "المملكة المتحدة", "en": "United Kingdom"},
    "FR": {"ar": "فرنسا", "en": "France"},
    "DE": {"ar": "ألمانيا", "en": "Germany"},
    "IR": {"ar": "إيران", "en": "Iran"},
    "MY": {"ar": "ماليزيا", "en": "Malaysia"},
    "ID": {"ar": "إندونيسيا", "en": "Indonesia"},
    "SG": {"ar": "سنغافورة", "en": "Singapore"},
}


def country_name(code: str, lang: str = "ar") -> str:
    return COUNTRY_NAMES.get(code.upper(), {}).get(lang, code)


def is_country_allowed(country_code: str) -> bool:
    """
    Check if a country ISO code is permitted.
    ALLOWED_COUNTRIES == []  (empty .env value)  ->  all countries allowed.
    Read from config at call time so runtime changes are respected.
    """
    allowed = _config.ALLOWED_COUNTRIES   # live read, not cached at import
    if not allowed:
        return True
    if not country_code:
        return True
    return country_code.upper() in [c.upper() for c in allowed]


async def _geocode(query: str):
    """Run Nominatim geocode in thread pool (it's blocking)."""
    return await asyncio.to_thread(_get_geolocator().geocode, query)


def _extract_country_code(location) -> str:
    """Extract ISO country code from a Nominatim location object."""
    try:
        raw = location.raw
        country_code = raw.get("address", {}).get("country_code", "").upper()
        if not country_code:
            # Fallback: try last part of display_name
            parts = location.address.split(", ")
            country_code = parts[-1].strip().upper()[:2]
        return country_code
    except Exception:
        return ""


async def geocode_city(query: str) -> Optional[dict]:
    try:
        from slugify import slugify
    except ImportError:
        def slugify(s, **kw): return s.lower().replace(" ","-")
    """
    Returns dict with: city, country, country_code, lat, lon, timezone
    or None if not found / not allowed.
    """
    loc = await _geocode(query)
    if not loc:
        # Try transliterated
        loc = await _geocode(slugify(query, separator=" "))
    if not loc:
        return None

    country_code = _extract_country_code(loc)
    tz = _get_tf().timezone_at(lng=loc.longitude, lat=loc.latitude) or "UTC"

    # Split city from address
    city = query.split(",")[0].strip()
    # Try to get proper city name from address
    try:
        parts = loc.address.split(", ")
        city = parts[0].strip() if parts else city
    except Exception:
        pass

    country = country_name(country_code, "en")

    return {
        "city": city,
        "country": country,
        "country_code": country_code,
        "lat": loc.latitude,
        "lon": loc.longitude,
        "timezone": tz,
    }


def get_preset(city_ar: str) -> Optional[tuple]:
    """Returns (lat, lon, tz, country_code) for a preset Saudi city."""
    return SA_CITIES.get(city_ar)
