"""
services/reminders.py — محرك التذكيرات (مُحسَّن لـ 500K مستخدم، ملتزم بحدود Telegram API)

Telegram rate-limit strategy:
  • TG_SEND_DELAY (0.04 s) بين كل رسالة → أقصاه 25 رسالة/ثانية (الحد 30).
  • عند 429 RetryAfter  → ننتظر المدة التي يطلبها Telegram تحديداً ثم نعيد.
  • عند أي خطأ آخر     → exponential back-off حتى TG_RETRY_MAX مرات.
  • المستخدمون الذين حظروا البوت يُسجَّلون ويُتجاهلون في الدورة التالية.
  • المعالجة تسلسلية داخل كل دُفعة (لا asyncio.gather على الإرسال) لضمان
    عدم تجاوز السرعة الكلية.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Optional

import pytz
from telegram.error import RetryAfter, Forbidden, BadRequest

from config import (
    REMINDER_BATCH_SIZE,
    REMINDER_CHECK_INTERVAL,
    TG_SEND_DELAY,
    TG_RETRY_MAX,
    TG_RETRY_BASE,
)
from services.database import db
from services.prayer import PrayerService
from utils.helpers import esc, fmt_time, prayer_display

logger = logging.getLogger(__name__)


class ReminderEngine:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._bot = None
        # Track users who blocked the bot → skip until they /start again
        self._blocked: set[int] = set()

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def start(self, bot) -> None:
        self._bot = bot
        self._task = asyncio.create_task(self._loop())
        logger.info("✅ Reminder engine started.")

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    # ── Main loop ─────────────────────────────────────────────────────────────
    async def _loop(self) -> None:
        while True:
            try:
                await self._check_all()
            except asyncio.CancelledError:
                logger.info("[reminders] Engine stopped.")
                break
            except Exception as e:
                logger.error(f"[reminders] Loop error: {e}")
            await asyncio.sleep(REMINDER_CHECK_INTERVAL)

    # ── Scan all reminder users ────────────────────────────────────────────────
    async def _check_all(self) -> None:
        users = await db.get_users_with_reminders()
        if not users:
            return

        # Exclude known-blocked users
        active = [u for u in users if u["user_id"] not in self._blocked]
        logger.debug(
            f"[reminders] Checking {len(active)} users "
            f"({len(users) - len(active)} blocked/skipped)."
        )

        # Sequential batches — NO concurrent burst sends
        for i in range(0, len(active), REMINDER_BATCH_SIZE):
            batch = active[i : i + REMINDER_BATCH_SIZE]
            for user in batch:
                await self._check_user(user)
            # Yield between batches so other coroutines can run
            await asyncio.sleep(0)

    # ── Per-user check ─────────────────────────────────────────────────────────
    async def _check_user(self, user: dict) -> None:
        try:
            tz_name = user.get("timezone", "Asia/Riyadh")
            try:
                tz = pytz.timezone(tz_name)
            except Exception:
                tz = pytz.timezone("Asia/Riyadh")

            now_local  = datetime.now(tz).replace(second=0, microsecond=0)
            offset_min = int(user.get("reminder_offset", 10))
            enabled    = set(
                (user.get("reminder_prayers") or "Fajr,Dhuhr,Asr,Maghrib,Isha").split(",")
            )
            lang     = user.get("language", "ar")
            time_fmt = user.get("time_format", "12")
            user_id  = user["user_id"]

            upcoming = await PrayerService.upcoming(user_id, user)
            for name, p_time in upcoming:
                if name not in enabled:
                    continue
                delta_min = (p_time - now_local).total_seconds() / 60
                if abs(delta_min - offset_min) < 1.0:
                    await self._send_with_ratelimit(
                        user_id, name, p_time, offset_min, lang, time_fmt
                    )

        except Exception as e:
            logger.error(f"[reminders] User {user.get('user_id')} check error: {e}")

    # ── Rate-limited send ──────────────────────────────────────────────────────
    async def _send_with_ratelimit(
        self,
        user_id: int,
        prayer_name: str,
        prayer_time: datetime,
        offset: int,
        lang: str,
        time_fmt: str,
    ) -> None:
        """
        Send one reminder message respecting Telegram rate limits:
          1. Always wait TG_SEND_DELAY before each send (global pacing ≤ 25/s).
          2. On 429 RetryAfter → sleep exactly what Telegram requests, then retry.
          3. On other errors   → exponential back-off up to TG_RETRY_MAX attempts.
          4. On Forbidden      → mark blocked, disable reminders in DB.
        """
        await asyncio.sleep(TG_SEND_DELAY)   # pacing: ≤ 25 msg/sec global

        name_disp = prayer_display(prayer_name, lang)
        time_disp = fmt_time(prayer_time, time_fmt)
        msg = _build_reminder_msg(name_disp, offset, time_disp, lang)

        attempt = 0
        while attempt < TG_RETRY_MAX:
            attempt += 1
            try:
                await self._bot.send_message(
                    chat_id=user_id,
                    text=msg,
                    parse_mode="MarkdownV2",
                )
                logger.info(f"[reminders] ✅ {user_id}: {prayer_name}")
                return

            except RetryAfter as e:
                # Telegram told us exactly how long to wait — obey it precisely
                wait = float(e.retry_after) + 0.5
                logger.warning(
                    f"[reminders] 429 RetryAfter {wait:.1f}s "
                    f"(user={user_id}, attempt={attempt})"
                )
                await asyncio.sleep(wait)
                attempt -= 1   # RetryAfter doesn't consume a retry slot

            except Forbidden:
                logger.info(f"[reminders] {user_id} blocked bot — disabling reminders.")
                self._blocked.add(user_id)
                try:
                    await db.update_setting(user_id, "reminder_enabled", 0)
                except Exception:
                    pass
                return

            except BadRequest as e:
                logger.warning(f"[reminders] BadRequest {user_id}: {e}")
                return

            except Exception as e:
                if attempt < TG_RETRY_MAX:
                    sleep_for = TG_RETRY_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        f"[reminders] Error {user_id} attempt {attempt}: {e} "
                        f"— retry in {sleep_for:.1f}s"
                    )
                    await asyncio.sleep(sleep_for)
                else:
                    logger.error(
                        f"[reminders] Gave up on {user_id} after {TG_RETRY_MAX} attempts: {e}"
                    )


# ── Message builder ────────────────────────────────────────────────────────────
def _build_reminder_msg(name_disp: str, offset: int, time_disp: str, lang: str) -> str:
    if lang == "ar":
        return (
            f"🔔 *تذكير بالصلاة*\n\n"
            f"🕌 صلاة *{esc(name_disp)}* بعد *{esc(str(offset))}* دقيقة\n"
            f"⏰ الوقت: {esc(time_disp)}"
        )
    return (
        f"🔔 *Prayer Reminder*\n\n"
        f"🕌 *{esc(name_disp)}* prayer in *{esc(str(offset))}* minutes\n"
        f"⏰ Time: {esc(time_disp)}"
    )


reminder_engine = ReminderEngine()
