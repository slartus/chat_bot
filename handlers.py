import logging
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_CHAT_ID, TIMEZONE
from date_parser import parse_period
from db import get_personal_stats, get_stats, save_message

logger = logging.getLogger(__name__)

STATS_PATTERN = re.compile(r"статистика\s+за\s+(.+?)[\s!?.]*$", re.IGNORECASE)
PERSONAL_PATTERN = re.compile(r"моя\s+статистика", re.IGNORECASE)

HELP_TEXT = (
    "Я умею показывать статистику сообщений.\n\n"
    "Напиши:\n"
    "  статистика за сегодня\n"
    "  статистика за вчера\n"
    "  статистика за неделю\n"
    "  статистика за месяц\n"
    "  статистика за всё время\n"
    "  статистика за 12.03\n"
    "  статистика за 12.03.2026\n"
    "  статистика за 01.03-13.03\n"
    "  моя статистика"
)


def _fmt_num(n: int) -> str:
    """1240 → '1 240', 12304 → '12 304'"""
    return f"{n:,}".replace(",", "\u202f")


def _period_label(date_from: date | None, date_to: date | None) -> str:
    if date_from is None and date_to is None:
        return "всё время"
    if date_from == date_to:
        return date_from.strftime("%d.%m.%Y")
    return f"{date_from.strftime('%d.%m.%Y')} – {date_to.strftime('%d.%m.%Y')}"


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not msg or not user or not chat or user.is_bot:
        return

    text = msg.text or ""
    bot_username = context.bot.username

    if chat.id != ALLOWED_CHAT_ID:
        if text.lower().startswith(f"@{bot_username}".lower()):
            await msg.reply_text("Я работаю только в одной определённой группе.")
        return

    if text.lower().startswith(f"@{bot_username}".lower()):
        if PERSONAL_PATTERN.search(text):
            await handle_personal_stats(update)
        elif m := STATS_PATTERN.search(text):
            await handle_stats(update, m.group(1).strip())
        else:
            await msg.reply_text(HELP_TEXT)
        return

    tz = ZoneInfo(TIMEZONE)
    full_name = user.full_name or str(user.id)
    username = f"@{user.username}" if user.username else None

    try:
        await save_message(
            chat_id=chat.id,
            user_id=user.id,
            username=username,
            full_name=full_name,
            msg_date=datetime.now(tz).date(),
            length=len(text),
        )
    except Exception:
        logger.exception("Ошибка при сохранении сообщения")


async def handle_stats(update: Update, period_text: str):
    chat = update.effective_chat
    period = parse_period(period_text, TIMEZONE)

    if period is None:
        await update.effective_message.reply_text(HELP_TEXT)
        return

    date_from, date_to = period
    try:
        total, rows = await get_stats(chat.id, date_from, date_to)
    except Exception:
        logger.exception("Ошибка при получении статистики")
        await update.effective_message.reply_text("Произошла ошибка, попробуй позже.")
        return

    label = _period_label(date_from, date_to)

    if total == 0:
        await update.effective_message.reply_text(f"За {label} сообщений не найдено.")
        return

    lines = [f"Статистика за {label}:", f"Всего сообщений: {total}", ""]
    for display_name, count, length in rows:
        pct = round(count / total * 100)
        lines.append(f"{display_name} — {count} ({pct}%) · {_fmt_num(length)} симв.")

    await update.effective_message.reply_text("\n".join(lines))


async def handle_personal_stats(update: Update):
    chat = update.effective_chat
    user = update.effective_user

    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()

    try:
        personal, total = await get_personal_stats(chat.id, user.id, None, None)
        personal_today, _ = await get_personal_stats(chat.id, user.id, today, today)
    except Exception:
        logger.exception("Ошибка при получении личной статистики")
        await update.effective_message.reply_text("Произошла ошибка, попробуй позже.")
        return

    name = user.full_name or str(user.id)
    pct = round(personal / total * 100) if total else 0

    lines = [
        f"Статистика {name}:",
        f"Всего сообщений: {personal} ({pct}% от всех)",
        f"Сегодня: {personal_today}",
    ]
    await update.effective_message.reply_text("\n".join(lines))


async def post_daily_stats(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневная автоматическая сводка."""
    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()

    try:
        total, rows = await get_stats(ALLOWED_CHAT_ID, today, today)
    except Exception:
        logger.exception("Ошибка при публикации ежедневной сводки")
        return

    if total == 0:
        return

    label = _period_label(today, today)
    lines = [f"Итоги дня {label}:", f"Всего сообщений: {total}", ""]
    for display_name, count, length in rows:
        pct = round(count / total * 100)
        lines.append(f"{display_name} — {count} ({pct}%) · {_fmt_num(length)} симв.")

    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text="\n".join(lines))
