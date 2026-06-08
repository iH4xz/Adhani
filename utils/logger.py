"""
utils/logger.py — إعداد نظام السجلات (console + rotating file)

يُنشئ مجلد logs/ تلقائياً ويحتفظ بـ:
  • logs/adhani.log        — السجل الرئيسي (يُدار بـ RotatingFileHandler)
  • logs/adhani_error.log  — أخطاء ERROR وما فوق فقط
  • Console (stdout)       — كل المستويات INFO وما فوق

يُستدعى مرة واحدة عند بدء التشغيل: setup_logging()
"""
from __future__ import annotations
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# ── Constants ─────────────────────────────────────────────────────────────────
LOG_DIR        = os.getenv("LOG_DIR", "logs")
LOG_FILE       = os.path.join(LOG_DIR, "adhani.log")
LOG_ERROR_FILE = os.path.join(LOG_DIR, "adhani_error.log")

LOG_MAX_BYTES  = 10 * 1024 * 1024   # 10 MB per file
LOG_BACKUP_CNT = 5                   # keep 5 rotated copies

_FMT = "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """
    Call once at startup. Idempotent — safe to call multiple times.
    """
    global _configured
    if _configured:
        return
    _configured = True

    # Ensure log directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(_FMT, datefmt=_DATE)

    # ── Root logger ───────────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any handlers that basicConfig may have added already
    root.handlers.clear()

    # ── Console handler ───────────────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # ── Main rotating file handler (INFO+) ────────────────────────────────────
    file_h = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_CNT,
        encoding="utf-8",
    )
    file_h.setLevel(logging.INFO)
    file_h.setFormatter(formatter)
    root.addHandler(file_h)

    # ── Error-only rotating file handler ─────────────────────────────────────
    err_h = RotatingFileHandler(
        LOG_ERROR_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_CNT,
        encoding="utf-8",
    )
    err_h.setLevel(logging.ERROR)
    err_h.setFormatter(formatter)
    root.addHandler(err_h)

    # ── Silence noisy third-party loggers ─────────────────────────────────────
    for noisy in ("httpx", "httpcore", "geopy", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging initialised → console + {LOG_FILE} + {LOG_ERROR_FILE}"
    )
