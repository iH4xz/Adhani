"""
handlers/admin.py — لوحة تحكم المطوّر/المالك
"""
from __future__ import annotations
import glob
import logging
import os
import sys
from datetime import datetime

import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes

from config import (
    OWNER_ID, ALLOWED_COUNTRIES, STORAGE_DIR,
)
from services.database import db
from handlers.keyboards import admin_panel_kb
from utils.helpers import get_group_ids
from utils.i18n import t

logger = logging.getLogger(__name__)




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
