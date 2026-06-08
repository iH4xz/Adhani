"""
services/database.py — طبقة قاعدة البيانات مع الترحيل التلقائي

يدعم كلا الامتدادين:
  *.db     — ملفات النسخة الحالية
  *.sqlite — ملفات النسخة القديمة (v1) تُرحَّل وتُنقل تلقائياً
"""
from __future__ import annotations
import asyncio
import glob
import logging
import os
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

# ── Whitelist for update_setting ───────────────────────────────────────────────
_ALLOWED_USER_COLS = frozenset({
    "city", "country", "latitude", "longitude", "timezone",
    "method", "madhab", "time_format", "language", "date_pref",
    "reminder_enabled", "reminder_offset", "reminder_prayers",
    "timings_cache", "cache_date", "last_updated",
})

# ── User shard migrations (append-only!) ──────────────────────────────────────
USER_MIGRATIONS: list[tuple[int, str]] = [
    (1, """CREATE TABLE IF NOT EXISTS user_settings (
        user_id           INTEGER PRIMARY KEY,
        city              TEXT,
        country           TEXT,
        latitude          REAL,
        longitude         REAL,
        timezone          TEXT,
        method            INTEGER DEFAULT 4,
        madhab            TEXT    DEFAULT 'shafi',
        time_format       TEXT    DEFAULT '12',
        language          TEXT    DEFAULT 'ar',
        date_pref         TEXT    DEFAULT 'both',
        reminder_enabled  INTEGER DEFAULT 0,
        reminder_offset   INTEGER DEFAULT 10,
        reminder_prayers  TEXT    DEFAULT 'Fajr,Dhuhr,Asr,Maghrib,Isha',
        timings_cache     TEXT,
        cache_date        TEXT,
        last_updated      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""),
    # ── add future user migrations below ─────────────────────────────────────
    # (2, "ALTER TABLE user_settings ADD COLUMN new_col TEXT DEFAULT ''"),
]

# ── Group DB migrations ────────────────────────────────────────────────────────
GROUP_MIGRATIONS: list[tuple[int, str]] = [
    (1, """CREATE TABLE IF NOT EXISTS group_settings (
        group_id     INTEGER PRIMARY KEY,
        city         TEXT,
        country      TEXT,
        latitude     REAL,
        longitude    REAL,
        timezone     TEXT,
        method       INTEGER DEFAULT 4,
        language     TEXT    DEFAULT 'ar',
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""),
]

USER_DEFAULTS = {
    "city": "مكة المكرمة", "country": "Saudi Arabia",
    "latitude": 21.3891, "longitude": 39.8579,
    "timezone": "Asia/Riyadh", "method": 4,
    "madhab": "shafi", "time_format": "12",
    "language": "ar", "date_pref": "both",
    "reminder_enabled": 0, "reminder_offset": 10,
    "reminder_prayers": "Fajr,Dhuhr,Asr,Maghrib,Isha",
    "timings_cache": None, "cache_date": None,
}


# ── Core migration engine ──────────────────────────────────────────────────────
async def _apply_migrations(db: aiosqlite.Connection,
                             migrations: list[tuple[int, str]],
                             label: str) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            id      INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL DEFAULT 0
        )
    """)
    await db.execute("INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 0)")
    async with db.execute("SELECT version FROM schema_version WHERE id = 1") as cur:
        row = await cur.fetchone()
    current = row[0] if row else 0
    applied = 0
    for ver, sql in sorted(migrations, key=lambda x: x[0]):
        if ver <= current:
            continue
        try:
            await db.execute(sql.strip())
            await db.execute("UPDATE schema_version SET version=? WHERE id=1", (ver,))
            logger.info(f"[db] {label}: applied v{ver}")
            applied += 1
        except aiosqlite.OperationalError as e:
            if "duplicate column" in str(e).lower():
                logger.warning(f"[db] {label} v{ver}: column exists, skipping")
                await db.execute("UPDATE schema_version SET version=? WHERE id=1", (ver,))
            else:
                logger.error(f"[db] {label} v{ver} FAILED: {e}")
                raise
    if applied:
        await db.commit()


class DatabaseRouter:
    def __init__(self, storage_dir: str = "storage"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}

    # ── Path helpers ───────────────────────────────────────────────────────────
    def _user_path(self, user_id: int) -> str:
        shard = user_id // 100
        return os.path.join(self.storage_dir, f"users_{shard}.db")

    def _group_path(self, group_id: int) -> str:
        return os.path.join(self.storage_dir, f"group_{group_id}.db")

    def _lock(self, path: str) -> asyncio.Lock:
        if path not in self._locks:
            self._locks[path] = asyncio.Lock()
        return self._locks[path]

    def _all_user_dbs(self) -> list[str]:
        """Return ALL user shard paths — both .db and legacy .sqlite"""
        return (
            glob.glob(os.path.join(self.storage_dir, "users_*.db")) +
            glob.glob(os.path.join(self.storage_dir, "users_shard_*.sqlite")) +  # v1 pattern
            glob.glob(os.path.join(self.storage_dir, "*.sqlite"))                # any other sqlite
        )

    def _all_group_dbs(self) -> list[str]:
        return (
            glob.glob(os.path.join(self.storage_dir, "group_*.db")) +
            glob.glob(os.path.join(self.storage_dir, "group_*.sqlite"))
        )

    # ── Init per file ──────────────────────────────────────────────────────────
    async def _init_user_db(self, user_id: int) -> None:
        path = self._user_path(user_id)
        async with self._lock(path):
            async with aiosqlite.connect(path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await _apply_migrations(db, USER_MIGRATIONS,
                                        f"user_shard:{os.path.basename(path)}")

    async def _init_group_db(self, group_id: int) -> None:
        path = self._group_path(group_id)
        async with self._lock(path):
            async with aiosqlite.connect(path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await _apply_migrations(db, GROUP_MIGRATIONS, f"group:{group_id}")

    # ── Startup: migrate existing + import legacy .sqlite data ────────────────
    async def migrate_all(self) -> None:
        """
        1. Migrate all existing .db shards (new format).
        2. Find all legacy .sqlite files, migrate their schema, then copy
           every row into the correct .db shard file, then rename the .sqlite
           to .sqlite.migrated so it won't be processed again.
        """
        # ── New .db shards ────────────────────────────────────────────────────
        new_user_dbs  = glob.glob(os.path.join(self.storage_dir, "users_*.db"))
        new_group_dbs = glob.glob(os.path.join(self.storage_dir, "group_*.db"))

        for path in new_user_dbs:
            await self._migrate_file(path, USER_MIGRATIONS)
        for path in new_group_dbs:
            await self._migrate_file(path, GROUP_MIGRATIONS)

        # ── Legacy .sqlite files ───────────────────────────────────────────────
        legacy_patterns = [
            (os.path.join(self.storage_dir, "users_shard_*.sqlite"), "user"),
            (os.path.join(self.storage_dir, "users_*.sqlite"),       "user"),
            (os.path.join(self.storage_dir, "group_*.sqlite"),       "group"),
        ]
        imported_users  = 0
        imported_groups = 0
        legacy_files    = 0

        for pattern, kind in legacy_patterns:
            for old_path in glob.glob(pattern):
                if old_path.endswith(".migrated"):
                    continue
                legacy_files += 1
                if kind == "user":
                    imported_users += await self._import_legacy_users(old_path)
                else:
                    imported_groups += await self._import_legacy_groups(old_path)
                # Rename so we don't process it again
                os.rename(old_path, old_path + ".migrated")
                logger.info(f"[db] Legacy file migrated and renamed: {old_path}")

        logger.info(
            f"[db] Startup migration complete: "
            f"{len(new_user_dbs)} user shards, {len(new_group_dbs)} group DBs, "
            f"{legacy_files} legacy files imported "
            f"({imported_users} users, {imported_groups} groups)."
        )

    async def _migrate_file(self, path: str, migrations: list) -> None:
        async with self._lock(path):
            try:
                async with aiosqlite.connect(path) as db:
                    await db.execute("PRAGMA journal_mode=WAL")
                    await _apply_migrations(db, migrations,
                                            f"startup:{os.path.basename(path)}")
            except Exception as e:
                logger.error(f"[db] Migration failed for {path}: {e}")

    async def _import_legacy_users(self, old_path: str) -> int:
        """Copy rows from a legacy user .sqlite into the correct .db shards."""
        count = 0
        try:
            async with aiosqlite.connect(old_path) as old_db:
                old_db.row_factory = aiosqlite.Row
                # Detect table name — v1 used user_settings
                async with old_db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ) as cur:
                    tables = [r[0] for r in await cur.fetchall()]
                if "user_settings" not in tables:
                    logger.warning(f"[db] No user_settings in {old_path}, skipping.")
                    return 0

                async with old_db.execute("SELECT * FROM user_settings") as cur:
                    rows = await cur.fetchall()

                for row in rows:
                    d = dict(row)
                    user_id = d.get("user_id")
                    if not user_id:
                        continue
                    await self._init_user_db(user_id)
                    new_path = self._user_path(user_id)
                    async with aiosqlite.connect(new_path) as new_db:
                        # Insert or ignore — don't overwrite newer data
                        await new_db.execute("""
                            INSERT OR IGNORE INTO user_settings
                                (user_id, city, country, latitude, longitude, timezone,
                                 method, madhab, time_format, language, date_pref,
                                 reminder_enabled, reminder_offset, reminder_prayers,
                                 timings_cache, cache_date, last_updated)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            user_id,
                            d.get("city"), d.get("country"),
                            d.get("latitude"), d.get("longitude"),
                            d.get("timezone"),
                            d.get("method", 4),
                            d.get("madhab", "shafi"),
                            d.get("time_format", "12"),
                            d.get("language", "ar"),
                            d.get("date_pref", "both"),
                            d.get("reminder_enabled", 0),
                            d.get("reminder_offset", 10),
                            d.get("reminder_prayers", "Fajr,Dhuhr,Asr,Maghrib,Isha"),
                            None, None,   # always clear cache on migration
                            d.get("last_updated"),
                        ))
                        await new_db.commit()
                    count += 1
        except Exception as e:
            logger.error(f"[db] Failed to import {old_path}: {e}")
        return count

    async def _import_legacy_groups(self, old_path: str) -> int:
        """Copy rows from a legacy group .sqlite into the correct .db files."""
        count = 0
        try:
            async with aiosqlite.connect(old_path) as old_db:
                old_db.row_factory = aiosqlite.Row
                async with old_db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ) as cur:
                    tables = [r[0] for r in await cur.fetchall()]
                if "group_settings" not in tables:
                    return 0
                async with old_db.execute("SELECT * FROM group_settings") as cur:
                    rows = await cur.fetchall()
                for row in rows:
                    d = dict(row)
                    group_id = d.get("group_id")
                    if not group_id:
                        continue
                    await self._init_group_db(group_id)
                    new_path = self._group_path(group_id)
                    async with aiosqlite.connect(new_path) as new_db:
                        await new_db.execute("""
                            INSERT OR IGNORE INTO group_settings
                                (group_id, city, country, latitude, longitude, timezone,
                                 method, language, last_updated)
                            VALUES (?,?,?,?,?,?,?,?,?)
                        """, (
                            group_id,
                            d.get("city"), d.get("country"),
                            d.get("latitude"), d.get("longitude"),
                            d.get("timezone"),
                            d.get("method", 4),
                            d.get("language", "ar"),
                            d.get("last_updated"),
                        ))
                        await new_db.commit()
                    count += 1
        except Exception as e:
            logger.error(f"[db] Failed to import {old_path}: {e}")
        return count

    # ── CRUD — Users ───────────────────────────────────────────────────────────
    async def upsert_user(self, user_id: int, city: str, country: str,
                          lat: float, lon: float, tz: str) -> None:
        await self._init_user_db(user_id)
        path = self._user_path(user_id)
        async with aiosqlite.connect(path) as db:
            await db.execute("""
                INSERT INTO user_settings
                    (user_id, city, country, latitude, longitude, timezone,
                     timings_cache, cache_date)
                VALUES (?,?,?,?,?,?,NULL,NULL)
                ON CONFLICT(user_id) DO UPDATE SET
                    city=excluded.city, country=excluded.country,
                    latitude=excluded.latitude, longitude=excluded.longitude,
                    timezone=excluded.timezone,
                    timings_cache=NULL, cache_date=NULL,
                    last_updated=CURRENT_TIMESTAMP
            """, (user_id, city, country, lat, lon, tz))
            await db.commit()

    async def get_user(self, user_id: int) -> dict:
        await self._init_user_db(user_id)
        path = self._user_path(user_id)
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM user_settings WHERE user_id=?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else dict(USER_DEFAULTS)

    async def update_setting(self, user_id: int, key: str, value) -> None:
        if key not in _ALLOWED_USER_COLS:
            raise ValueError(f"Disallowed column: {key}")
        await self._init_user_db(user_id)
        path = self._user_path(user_id)
        async with aiosqlite.connect(path) as db:
            await db.execute(
                f"UPDATE user_settings SET {key}=? WHERE user_id=?",
                (value, user_id)
            )
            await db.commit()

    async def update_cache(self, user_id: int, cache_json: str, date_str: str) -> None:
        await self._init_user_db(user_id)
        path = self._user_path(user_id)
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "UPDATE user_settings SET timings_cache=?, cache_date=? WHERE user_id=?",
                (cache_json, date_str, user_id)
            )
            await db.commit()

    async def get_all_users(self) -> list[int]:
        ids: set[int] = set()
        for path in glob.glob(os.path.join(self.storage_dir, "users_*.db")):
            try:
                async with aiosqlite.connect(path) as db:
                    async with db.execute("SELECT user_id FROM user_settings") as cur:
                        async for row in cur:
                            ids.add(row[0])
            except Exception as e:
                logger.warning(f"get_all_users: {path}: {e}")
        return list(ids)

    async def get_users_with_reminders(self) -> list[dict]:
        users = []
        for path in glob.glob(os.path.join(self.storage_dir, "users_*.db")):
            try:
                async with aiosqlite.connect(path) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute(
                        "SELECT * FROM user_settings "
                        "WHERE reminder_enabled=1 AND latitude IS NOT NULL"
                    ) as cur:
                        async for row in cur:
                            users.append(dict(row))
            except Exception as e:
                logger.warning(f"get_users_with_reminders: {path}: {e}")
        return users

    async def get_total_users(self) -> int:
        return len(await self.get_all_users())

    async def get_reminder_count(self) -> int:
        return len(await self.get_users_with_reminders())

    async def get_active_countries(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for path in glob.glob(os.path.join(self.storage_dir, "users_*.db")):
            try:
                async with aiosqlite.connect(path) as db:
                    async with db.execute("SELECT country FROM user_settings") as cur:
                        async for row in cur:
                            c = row[0] or "Unknown"
                            counts[c] = counts.get(c, 0) + 1
            except Exception as e:
                logger.warning(f"get_active_countries: {path}: {e}")
        return counts

    # ── CRUD — Groups ──────────────────────────────────────────────────────────
    async def upsert_group(self, group_id: int, city: str, country: str,
                           lat: float, lon: float, tz: str) -> None:
        await self._init_group_db(group_id)
        path = self._group_path(group_id)
        async with aiosqlite.connect(path) as db:
            await db.execute("""
                INSERT INTO group_settings
                    (group_id, city, country, latitude, longitude, timezone)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(group_id) DO UPDATE SET
                    city=excluded.city, country=excluded.country,
                    latitude=excluded.latitude, longitude=excluded.longitude,
                    timezone=excluded.timezone,
                    last_updated=CURRENT_TIMESTAMP
            """, (group_id, city, country, lat, lon, tz))
            await db.commit()

    async def get_group(self, group_id: int) -> dict:
        await self._init_group_db(group_id)
        path = self._group_path(group_id)
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM group_settings WHERE group_id=?", (group_id,)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else {}


# Singleton
db = DatabaseRouter()
