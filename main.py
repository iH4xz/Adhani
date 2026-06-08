"""
main.py — نقطة دخول بوت أذاني
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
وضع التشغيل يُحدَّد تلقائياً من .env:
  WEBHOOK_URL مضبوط  → Webhook  (uvicorn main:app  أو  python main.py)
  WEBHOOK_URL فارغ   → Polling  (python main.py)
"""

# ── 1. Logging — أول شيء قبل أي import آخر ──────────────────────────────────
import sys
import traceback

try:
    from utils.logger import setup_logging
    setup_logging()
except Exception as _log_err:
    import logging
    logging.basicConfig(
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        level=logging.INFO,
        stream=sys.stdout,
    )
    logging.getLogger(__name__).warning(f"Could not init file logger: {_log_err}")

import logging
logger = logging.getLogger(__name__)

# ── 2. Guard: catch ALL import/startup errors so they show in the log ─────────
try:
    from warnings import filterwarnings
    from telegram.warnings import PTBUserWarning
    filterwarnings("ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

    from config import TOKEN, WEBHOOK_URL, PORT, WEBHOOK_SECRET
    from config import SELECTING_ACTION, TYPING_CUSTOM_CITY

    if not TOKEN:
        logger.critical("❌  TELEGRAM_TOKEN غير موجود في .env")
        sys.exit(1)

    logger.info(f"Mode: {'WEBHOOK' if WEBHOOK_URL else 'POLLING'} | "
                f"Port: {PORT} | Token: ...{TOKEN[-6:]}")

    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        ConversationHandler,
        InlineQueryHandler,
        filters,
    )

    from services.database import db
    from services.reminders import reminder_engine
    from handlers.start import start_command, handle_typed_city, cancel
    from handlers.prayer_cmds import a_command, schedule_command, adhani_trigger
    from handlers.settings import (
        my_command, settings_command, help_command, button_handler
    )
    from handlers.reminder_cmd import reminder_command
    from handlers.group import g_command
    from handlers.admin import (
        admin_command, stats_command, admin_callback,
    )
    from handlers.inline import inline_handler

except Exception:
    logger.critical("❌ Fatal error during startup imports:\n" + traceback.format_exc())
    sys.exit(1)


# ── 3. Register handlers (shared by both modes) ───────────────────────────────
def _register_handlers(ptb: Application) -> None:
    city_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            SELECTING_ACTION: [CallbackQueryHandler(button_handler)],
            TYPING_CUSTOM_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_typed_city)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )
    ptb.add_handler(city_conv)
    ptb.add_handler(CommandHandler("help",     help_command))
    ptb.add_handler(CommandHandler("my",       my_command))
    ptb.add_handler(CommandHandler("settings", settings_command))
    ptb.add_handler(CommandHandler("a",        a_command))
    ptb.add_handler(CommandHandler("schedule", schedule_command))
    ptb.add_handler(CommandHandler("reminder", reminder_command))
    ptb.add_handler(CommandHandler("g",        g_command))
    ptb.add_handler(CommandHandler("admin",    admin_command))
    ptb.add_handler(CommandHandler("stats",    stats_command))
    ptb.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin\|"))
    ptb.add_handler(CallbackQueryHandler(button_handler))
    ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, adhani_trigger))
    ptb.add_handler(InlineQueryHandler(inline_handler))
    logger.debug("All handlers registered.")


# =============================================================================
# MODE A — WEBHOOK via FastAPI + uvicorn
# Start: uvicorn main:app --host 0.0.0.0 --port 8000
#    or: python main.py  (when WEBHOOK_URL is set)
# =============================================================================
if WEBHOOK_URL:
    try:
        from contextlib import asynccontextmanager
        from fastapi import FastAPI, Request, Response
    except ImportError:
        logger.critical("❌ fastapi / uvicorn not installed. Run: pip install fastapi uvicorn[standard]")
        sys.exit(1)

    _ptb_app: Application | None = None

    @asynccontextmanager
    async def _lifespan(application: FastAPI):
        global _ptb_app
        logger.info("▶️  WEBHOOK mode startup...")
        try:
            await db.migrate_all()

            _ptb_app = Application.builder().token(TOKEN).build()
            _register_handlers(_ptb_app)
            await _ptb_app.initialize()
            await _ptb_app.start()

            endpoint = f"{WEBHOOK_URL.rstrip('/')}/{TOKEN}"
            await _ptb_app.bot.set_webhook(
                endpoint,
                secret_token=WEBHOOK_SECRET or None,
                drop_pending_updates=True,
            )
            logger.info(f"✅ Webhook → {endpoint[:60]}...")
            reminder_engine.start(_ptb_app.bot)
            logger.info("🚀 Adhani Bot (Webhook) running.")
        except Exception:
            logger.critical("❌ Webhook startup failed:\n" + traceback.format_exc())
            raise

        yield  # ← uvicorn serves here

        logger.info("🛑 Shutdown...")
        reminder_engine.stop()
        if _ptb_app:
            try:
                await _ptb_app.stop()
                await _ptb_app.shutdown()
            except Exception as e:
                logger.warning(f"PTB shutdown error: {e}")
        logger.info("🛑 Adhani Bot stopped.")

    app = FastAPI(title="Adhani Bot", lifespan=_lifespan,
                  docs_url=None, redoc_url=None)

    @app.post(f"/{TOKEN}")
    async def _webhook_endpoint(req: Request) -> Response:
        incoming = req.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if WEBHOOK_SECRET and incoming != WEBHOOK_SECRET:
            logger.warning(f"Webhook: bad secret from {req.client.host if req.client else '?'}")
            return Response(status_code=403)
        try:
            data = await req.json()
            await _ptb_app.process_update(Update.de_json(data, _ptb_app.bot))
        except Exception as e:
            logger.error(f"Webhook processing error: {e}", exc_info=True)
        return Response(status_code=200)

    @app.get("/health")
    async def _health() -> dict:
        return {"status": "ok", "mode": "webhook", "bot": "adhani"}

    # Allow running directly: python main.py (in addition to uvicorn main:app)
    if __name__ == "__main__":
        try:
            import uvicorn
            logger.info(f"Starting uvicorn on 0.0.0.0:{PORT}")
            uvicorn.run(app, host="0.0.0.0", port=PORT)
        except Exception:
            logger.critical("❌ uvicorn failed:\n" + traceback.format_exc())
            sys.exit(1)


# =============================================================================
# MODE B — POLLING
# Start: python main.py  (when WEBHOOK_URL is empty)
#
# PTB 20+/22.x rule: run_polling() owns the event loop.
# NEVER call it inside asyncio.run() — that creates a nested loop crash.
# Pre-startup async work (DB migration) runs in a disposable loop that is
# fully closed before PTB's loop starts.
# =============================================================================
else:
    def _run_polling() -> None:
        import asyncio

        logger.info("▶️  POLLING mode startup...")

        # Run async init in a throwaway loop — close it entirely before PTB starts
        try:
            _pre = asyncio.new_event_loop()
            asyncio.set_event_loop(_pre)
            _pre.run_until_complete(db.migrate_all())
            _pre.close()
            asyncio.set_event_loop(None)   # make sure no stale loop reference remains
        except Exception:
            logger.critical("❌ DB migration failed:\n" + traceback.format_exc())
            sys.exit(1)

        try:
            polling_app = Application.builder().token(TOKEN).build()
            _register_handlers(polling_app)

            async def _post_init(application: Application) -> None:
                reminder_engine.start(application.bot)
                logger.info("🚀 Adhani Bot (Polling) running. Ctrl+C to stop.")

            polling_app.post_init = _post_init

            # run_polling() creates & manages its own event loop — do not wrap
            polling_app.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
            )
        except KeyboardInterrupt:
            logger.info("🛑 Stopped by user.")
        except Exception:
            logger.critical("❌ Polling crashed:\n" + traceback.format_exc())
            sys.exit(1)

    if __name__ == "__main__":
        _run_polling()
