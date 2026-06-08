"""
handlers/admin.py — لوحة تحكم المطوّر/المالك
"""
from __future__ import annotations
import asyncio
import glob
import logging
import os
import sys
from datetime import datetime

import aiosqlite
from telegram import Update
from telegram.error import RetryAfter, Forbidden
from telegram.ext import ContextTypes

from config import (
    OWNER_ID, ALLOWED_COUNTRIES, STORAGE_DIR, AWAITING_BROADCAST,
    BROADCAST_CHUNK, BROADCAST_CHUNK_SLEEP, TG_SEND_DELAY,
    TG_RETRY_MAX, TG_RETRY_BASE,
)
from services.database import db
from handlers.keyboards import admin_panel_kb, broadcast_confirm_kb
from utils.helpers import get_group_ids
from utils.i18n import t

logger = logging.getLogger(__name__)

_broadcast_draft: dict[int, str] = {}


def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


# ── /admin ─────────────────────────────────────────────────────────────────────
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user.id):
        await update.message.reply_text(t("unauthorized", "ar"))
        return
    await update.message.reply_text(
        "🛠 *لوحة تحكم أذاني*",
        reply_markup=admin_panel_kb(),
    )


# ── /stats ─────────────────────────────────────────────────────────────────────
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user.id):
        # await update.message.reply_text(t("unauthorized", "ar"))
        return
    await _send_stats(update, context, is_callback=False)


async def _send_stats(update, context, is_callback: bool = False) -> None:
    total     = await db.get_total_users()
    groups    = len(get_group_ids())
    reminders = await db.get_reminder_count()
    countries = await db.get_active_countries()
    country_lines = "\n".join(
        f"  • {c}: {n}" for c, n in sorted(countries.items(), key=lambda x: -x[1])
    )
    msg = (
        f"📊 *إحصائيات أذاني*\n\n"
        f"👤 المستخدمون: {total}\n"
        f"👥 المجموعات: {groups}\n"
        f"🔔 لديهم تنبيهات: {reminders}\n"
        f"🌍 الدول النشطة:\n{country_lines or '  (لا توجد بيانات)'}\n\n"
        f"🌐 الدول المسموحة: {', '.join(ALLOWED_COUNTRIES) or 'جميع الدول'}"
    )
    if is_callback:
        await update.callback_query.edit_message_text(
            msg, reply_markup=admin_panel_kb()
        )
    else:
        await update.message.reply_text(msg)


# ── /broadcast ConversationHandler entry ──────────────────────────────────────
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_owner(update.effective_user.id):
        await update.message.reply_text(t("unauthorized", "ar"))
        return -1
    await update.message.reply_text(t("broadcast_prompt", "ar"))
    return AWAITING_BROADCAST


async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if not _is_owner(user_id):
        return -1
    text = update.message.text or ""
    _broadcast_draft[user_id] = text
    preview = (
        f"📢 *معاينة الرسالة:*\n\n{text}\n\n"
        f"─────────────────\n"
        f"هل تريد الإرسال لجميع المستخدمين؟"
    )
    await update.message.reply_text(
        preview,
        reply_markup=broadcast_confirm_kb("ar"),
    )
    return AWAITING_BROADCAST


# ── Rate-limited broadcast sender ─────────────────────────────────────────────
async def _broadcast_send(bot, users: list[int], text: str) -> tuple[int, int]:
    """
    Send `text` to every user in `users`.
    Rate-limit rules:
      • TG_SEND_DELAY between every send (≤ 25 msg/sec global).
      • After BROADCAST_CHUNK sends, pause BROADCAST_CHUNK_SLEEP seconds.
      • On 429 RetryAfter → sleep exactly what Telegram asks, retry (no retry slot used).
      • On Forbidden (blocked) → skip silently.
      • On other errors → exponential back-off, up to TG_RETRY_MAX retries.
    Returns (sent_count, failed_count).
    """
    sent = 0
    failed = 0

    for idx, uid in enumerate(users, 1):
        # Chunk pause (breathing room every N messages)
        if idx > 1 and (idx - 1) % BROADCAST_CHUNK == 0:
            await asyncio.sleep(BROADCAST_CHUNK_SLEEP)
        else:
            await asyncio.sleep(TG_SEND_DELAY)

        attempt = 0
        while attempt < TG_RETRY_MAX:
            attempt += 1
            try:
                await bot.send_message(chat_id=uid, text=text)
                sent += 1
                break

            except RetryAfter as e:
                wait = float(e.retry_after) + 0.5
                logger.warning(f"[broadcast] 429 RetryAfter {wait:.1f}s (uid={uid})")
                await asyncio.sleep(wait)
                attempt -= 1   # doesn't count as a retry

            except Forbidden:
                # User blocked the bot
                failed += 1
                try:
                    await db.update_setting(uid, "reminder_enabled", 0)
                except Exception:
                    pass
                break

            except Exception as e:
                if attempt < TG_RETRY_MAX:
                    sleep_for = TG_RETRY_BASE * (2 ** (attempt - 1))
                    logger.warning(f"[broadcast] Error uid={uid} attempt={attempt}: {e} — retry in {sleep_for:.1f}s")
                    await asyncio.sleep(sleep_for)
                else:
                    logger.error(f"[broadcast] Gave up uid={uid}: {e}")
                    failed += 1

    return sent, failed


# ── Admin callback router ──────────────────────────────────────────────────────
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    if not _is_owner(user_id):
        await query.answer("❌ غير مصرح")
        return
    await query.answer()

    parts = query.data.split("|")
    sub = parts[1] if len(parts) > 1 else ""

    if sub == "stats":
        await _send_stats(update, context, is_callback=True)

    elif sub == "groups":
        ids = get_group_ids()
        lines = "\n".join(str(i) for i in ids[:50])
        extra = f"\n... و{len(ids) - 50} أخرى" if len(ids) > 50 else ""
        msg = f"👥 *المجموعات المسجّلة:* {len(ids)}\n\n{lines}{extra}"
        await query.edit_message_text(msg, reply_markup=admin_panel_kb())

    elif sub == "broadcast":
        await query.edit_message_text(t("broadcast_prompt", "ar"))
        context.user_data["admin_state"] = "awaiting_broadcast"

    elif sub == "broadcast_confirm":
        draft = _broadcast_draft.pop(user_id, None)
        if not draft:
            await query.edit_message_text("⚠️ لا توجد رسالة محفوظة.", reply_markup=admin_panel_kb())
            return

        all_users = await db.get_all_users()
        total = len(all_users)

        # Acknowledge quickly — long-running task follows
        await query.edit_message_text(
            f"📢 جارٍ الإرسال لـ {total} مستخدم...\n(سيتم إخطارك عند الانتهاء)"
        )

        # Run broadcast in background task so webhook doesn't time out
        async def _do_broadcast():
            sent, failed = await _broadcast_send(context.bot, all_users, draft)
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=t("broadcast_done", "ar", sent=sent, total=total)
                    + f"\n❌ فشل: {failed}",
                    reply_markup=admin_panel_kb(),
                )
            except Exception as e:
                logger.error(f"[broadcast] Could not notify admin: {e}")

        asyncio.create_task(_do_broadcast())

    elif sub == "broadcast_cancel":
        _broadcast_draft.pop(user_id, None)
        await query.edit_message_text("❌ تم إلغاء الإذاعة.", reply_markup=admin_panel_kb())

    elif sub == "clearcache":
        shards = glob.glob(os.path.join(STORAGE_DIR, "users_*.db"))
        cleared = 0
        for path in shards:
            try:
                async with aiosqlite.connect(path) as dbconn:
                    cur = await dbconn.execute(
                        "UPDATE user_settings SET timings_cache=NULL, cache_date=NULL"
                    )
                    cleared += cur.rowcount
                    await dbconn.commit()
            except Exception as e:
                logger.error(f"[clearcache] {path}: {e}")
        await query.edit_message_text(
            f"✅ تم مسح الكاش لـ {cleared} مستخدم.",
            reply_markup=admin_panel_kb(),
        )

    elif sub == "countries":
        allowed = ', '.join(ALLOWED_COUNTRIES) or "جميع الدول (بدون قيود)"
        msg = (
            f"🌍 *الدول المسموحة حالياً:*\n\n"
            f"`{allowed}`\n\n"
            f"_لتغييرها: عدّل ALLOWED\\_COUNTRIES في ملف .env_"
        )
        await query.edit_message_text(msg, reply_markup=admin_panel_kb())

    elif sub == "sysinfo":
        import platform
        shards    = len(glob.glob(os.path.join(STORAGE_DIR, "users_*.db")))
        group_dbs = len(glob.glob(os.path.join(STORAGE_DIR, "group_*.db")))
        msg = (
            f"🔧 *معلومات النظام*\n\n"
            f"Python: `{sys.version.split()[0]}`\n"
            f"OS: `{platform.system()} {platform.release()}`\n"
            f"Shards: `{shards}`\n"
            f"Group DBs: `{group_dbs}`\n"
            f"وقت الخادم: `{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}`"
        )
        await query.edit_message_text(msg, reply_markup=admin_panel_kb())
