import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_RANGE_RE = re.compile(r"^(.+?)\s*[-–]\s*(.+)$")


def parse_period(text: str, timezone: str) -> tuple[date | None, date | None] | None:
    """
    Парсит строку периода и возвращает (date_from, date_to).
    (None, None) означает "всё время".
    Возвращает None если не удалось распарсить.
    """
    tz = ZoneInfo(timezone)
    today = datetime.now(tz).date()

    text = text.strip().lower()

    if text in ("сегодня", "today"):
        return (today, today)

    if text in ("вчера", "yesterday"):
        d = today - timedelta(days=1)
        return (d, d)

    if text in ("неделю", "неделя", "week"):
        return (today - timedelta(days=6), today)

    if text in ("месяц", "month"):
        return (today - timedelta(days=29), today)

    if text in ("всё время", "все время", "all time"):
        return (None, None)

    # Сначала пробуем одиночную дату — чтобы "2026-03-13" не попало в диапазон
    d = _parse_single(text, today)
    if d:
        return (d, d)

    # Затем пробуем диапазон: "01.03-13.03" или "01.03.2026-13.03.2026"
    m = _RANGE_RE.match(text)
    if m:
        d1 = _parse_single(m.group(1), today)
        d2 = _parse_single(m.group(2), today)
        if d1 and d2:
            return (min(d1, d2), max(d1, d2))

    return None


def _parse_single(text: str, today: date) -> date | None:
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%d.%m", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt == "%d.%m":
                result = parsed.replace(year=today.year).date()
                if result > today:
                    result = result.replace(year=today.year - 1)
                return result
            return parsed.date()
        except ValueError:
            continue
    return None
