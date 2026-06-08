"""
utils/helpers.py — دوال مساعدة عامة
"""
from __future__ import annotations
import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ── Markdown escaping ──────────────────────────────────────────────────────────
def esc(text: str | None) -> str:
    """Escape MarkdownV2 special characters."""
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    return re.sub(r'([_\*\[\]()~`>#+\-=|{}.!\\])', r'\\\1', text)


# ── Time formatting ────────────────────────────────────────────────────────────
def fmt_time(dt: datetime, fmt: str = "12") -> str:
    if fmt == "24":
        return dt.strftime("%H:%M")
    return dt.strftime("%I:%M %p")


def fmt_remaining(diff: timedelta, lang: str = "ar") -> str:
    from utils.i18n import t
    total = int(diff.total_seconds())
    hours, rem = divmod(total, 3600)
    minutes, _ = divmod(rem, 60)
    if hours > 0:
        h_word = t("hours" if hours != 1 else "hour", lang)
        m_word = t("minutes", lang)
        return f"{hours} {h_word} {t('and', lang)} {minutes} {m_word}"
    return f"{minutes} {t('minutes', lang)}"


# ── Prayer name display ───────────────────────────────────────────────────────
def prayer_display(name: str, lang: str) -> str:
    from config import AR_PRAYER_NAMES
    if lang == "ar":
        return AR_PRAYER_NAMES.get(name, name)
    return name


# ── Group ID storage ──────────────────────────────────────────────────────────
def log_group_id(chat_id: int, groups_file: str = "storage/groups.txt") -> None:
    import os
    os.makedirs("storage", exist_ok=True)
    if not os.path.exists(groups_file):
        open(groups_file, "w").close()
    with open(groups_file, "r") as f:
        lines = f.read().splitlines()
    if str(chat_id) not in lines:
        with open(groups_file, "a") as f:
            f.write(f"{chat_id}\n")


def get_group_ids(groups_file: str = "storage/groups.txt") -> list[int]:
    import os
    if not os.path.exists(groups_file):
        return []
    with open(groups_file, "r") as f:
        return [int(l.strip()) for l in f if l.strip().isdigit()]
