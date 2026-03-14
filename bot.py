import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import ApplicationBuilder, MessageHandler, filters

from config import ADMIN_USER_ID, BOT_TOKEN, DAILY_STATS_HOUR, DAILY_STATS_MINUTE, TIMEZONE
from db import backfill_daily_stats, init_db
from handlers import on_message, post_daily_stats, send_db_backup

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def post_init(app):
    await init_db()
    inserted = await backfill_daily_stats()
    if inserted:
        logging.info(f"backfill_daily_stats: добавлено {inserted} строк")


if __name__ == "__main__":
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(MessageHandler(filters.TEXT, on_message))

    app.job_queue.run_daily(
        post_daily_stats,
        time=time(hour=DAILY_STATS_HOUR, minute=DAILY_STATS_MINUTE, tzinfo=ZoneInfo(TIMEZONE)),
    )

    if ADMIN_USER_ID:
        app.job_queue.run_daily(
            send_db_backup,
            time=time(hour=3, minute=0, tzinfo=ZoneInfo(TIMEZONE)),
            days=(0,),  # каждый понедельник
        )

    logging.info("Бот запущен")
    app.run_polling(drop_pending_updates=True)
