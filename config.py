import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
TIMEZONE = os.getenv("TIMEZONE", "UTC")
ALLOWED_CHAT_ID = int(os.environ["ALLOWED_CHAT_ID"])

_raw_time = os.getenv("DAILY_STATS_TIME", "23:59")
try:
    _h, _m = _raw_time.split(":")
    _h, _m = int(_h), int(_m)
    if not (0 <= _h <= 23 and 0 <= _m <= 59):
        raise ValueError
    DAILY_STATS_HOUR, DAILY_STATS_MINUTE = _h, _m
except (ValueError, AttributeError):
    raise ValueError(
        f"Неверный формат DAILY_STATS_TIME: {_raw_time!r}. Ожидается HH:MM (например 23:59)"
    )
