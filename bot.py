import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import ApplicationBuilder, MessageHandler, filters

from config import BOT_TOKEN, DAILY_STATS_HOUR, DAILY_STATS_MINUTE, TIMEZONE
from db import init_db
from handlers import on_message, post_daily_stats

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def post_init(app):
    await init_db()


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

    logging.info("Бот запущен")
    app.run_polling(drop_pending_updates=True)
