import aiosqlite
from dataclasses import dataclass
from datetime import date

DB_PATH = "messages.db"
SCHEMA_VERSION = 3


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        version = row[0]

        if version < 1:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    length INTEGER NOT NULL
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_date ON messages(chat_id, date)"
            )

        if version == 1:
            # Сбрасываем данные и пересоздаём таблицу с колонкой length
            await db.execute("DROP TABLE IF EXISTS messages")
            await db.execute("DROP INDEX IF EXISTS idx_chat_date")
            await db.execute("""
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    length INTEGER NOT NULL
                )
            """)
            await db.execute(
                "CREATE INDEX idx_chat_date ON messages(chat_id, date)"
            )

        if version < 3:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id      INTEGER NOT NULL,
                    user_id      INTEGER NOT NULL,
                    name         TEXT NOT NULL,
                    date         TEXT NOT NULL,
                    msg_count    INTEGER NOT NULL,
                    total_length INTEGER NOT NULL,
                    UNIQUE(chat_id, user_id, date)
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_chat_date ON daily_stats(chat_id, date)"
            )

        if version < SCHEMA_VERSION:
            await db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

        await db.commit()


async def save_message(
    chat_id: int,
    user_id: int,
    username: str | None,
    full_name: str,
    msg_date: date,
    length: int,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (chat_id, user_id, username, full_name, date, length) VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, user_id, username, full_name, msg_date.strftime("%Y-%m-%d"), length),
        )
        await db.commit()


def _date_condition(date_from: date | None, date_to: date | None) -> tuple[str, tuple]:
    if date_from is None and date_to is None:
        return "", ()
    return (
        "AND date BETWEEN ? AND ?",
        (date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d")),
    )


async def get_stats(
    chat_id: int, date_from: date | None, date_to: date | None
) -> tuple[int, list[tuple[int, str, int, int]]]:
    """Возвращает (total_msgs, [(user_id, display_name, count, total_length), ...])."""
    cond, params = _date_condition(date_from, date_to)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"""
            SELECT
                user_id,
                COALESCE(MAX(full_name), MAX(username)) AS display_name,
                COUNT(*) AS cnt,
                SUM(length) AS total_length
            FROM messages
            WHERE chat_id = ? {cond}
            GROUP BY user_id
            ORDER BY cnt DESC
            """,
            (chat_id, *params),
        )
        rows = await cursor.fetchall()

    total = sum(cnt for _, _, cnt, _ in rows)
    return total, rows


async def get_personal_stats(
    chat_id: int, user_id: int, date_from: date | None, date_to: date | None
) -> tuple[int, int]:
    """Возвращает (личных сообщений, всего сообщений) за период — одним запросом."""
    cond, params = _date_condition(date_from, date_to)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"""
            SELECT
                SUM(CASE WHEN user_id = ? THEN 1 ELSE 0 END),
                COUNT(*)
            FROM messages
            WHERE chat_id = ? {cond}
            """,
            (user_id, chat_id, *params),
        )
        row = await cursor.fetchone()

    return (row[0] or 0, row[1] or 0) if row else (0, 0)


async def save_daily_stats(
    chat_id: int,
    stats_date: date,
    rows: list[tuple[int, str, int, int]],
) -> None:
    """Сохраняет агрегат дня. rows: [(user_id, name, msg_count, total_length), ...]."""
    date_str = stats_date.strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            """
            INSERT OR REPLACE INTO daily_stats (chat_id, user_id, name, date, msg_count, total_length)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(chat_id, user_id, name, date_str, msg_count, total_length)
             for user_id, name, msg_count, total_length in rows],
        )
        await db.commit()


async def get_user_best_days(
    chat_id: int, user_id: int
) -> tuple[tuple[int, date] | None, tuple[int, date] | None]:
    """Возвращает (лучший день по сообщениям, лучший день по символам).
    Каждый элемент — (значение, дата) или None если данных нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT msg_count, date FROM daily_stats WHERE chat_id = ? AND user_id = ? ORDER BY msg_count DESC LIMIT 1",
            (chat_id, user_id),
        )
        row_msgs = await cursor.fetchone()

        cursor = await db.execute(
            "SELECT total_length, date FROM daily_stats WHERE chat_id = ? AND user_id = ? ORDER BY total_length DESC LIMIT 1",
            (chat_id, user_id),
        )
        row_len = await cursor.fetchone()

    best_msgs = (row_msgs[0], date.fromisoformat(row_msgs[1])) if row_msgs else None
    best_len = (row_len[0], date.fromisoformat(row_len[1])) if row_len else None
    return best_msgs, best_len


@dataclass
class RecordInfo:
    value: int
    record_date: date
    is_new: bool
    prev_value: int | None
    prev_date: date | None


@dataclass
class UserRecordInfo(RecordInfo):
    user_id: int
    name: str


async def get_daily_records(
    chat_id: int,
    stats_date: date,
) -> dict:
    """
    Возвращает рекорды по чату и пользователям.
    {
      "chat_msgs":    RecordInfo | None,
      "chat_length":  RecordInfo | None,
      "users_msgs":   list[UserRecordInfo],
      "users_length": list[UserRecordInfo],
    }
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT user_id, name, date, msg_count, total_length
            FROM daily_stats
            WHERE chat_id = ?
            ORDER BY date
            """,
            (chat_id,),
        )
        all_rows = await cursor.fetchall()

    if not all_rows:
        return {"chat_msgs": None, "chat_length": None, "users_msgs": [], "users_length": []}

    # Агрегируем чат по дням
    from collections import defaultdict
    chat_by_date: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    users_by_id: dict[int, list] = defaultdict(list)

    for user_id, name, d, msg_count, total_length in all_rows:
        prev_msgs, prev_len = chat_by_date[d]
        chat_by_date[d] = (prev_msgs + msg_count, prev_len + total_length)
        users_by_id[user_id].append((name, d, msg_count, total_length))

    def _build_chat_record(field_idx: int) -> RecordInfo | None:
        sorted_days = sorted(chat_by_date.items(), key=lambda x: x[1][field_idx], reverse=True)
        if not sorted_days:
            return None
        top_date_str, top_vals = sorted_days[0]
        top_val = top_vals[field_idx]
        top_date = date.fromisoformat(top_date_str)
        is_new = top_date == stats_date
        prev_val, prev_dt = None, None
        if is_new and len(sorted_days) > 1:
            prev_date_str, prev_vals = sorted_days[1]
            prev_val = prev_vals[field_idx]
            prev_dt = date.fromisoformat(prev_date_str)
        elif not is_new:
            prev_val, prev_dt = None, None
        return RecordInfo(
            value=top_val,
            record_date=top_date,
            is_new=is_new,
            prev_value=prev_val,
            prev_date=prev_dt,
        )

    def _build_user_records(field_idx: int) -> list[UserRecordInfo]:
        result = []
        for user_id, entries in users_by_id.items():
            name = entries[-1][0]
            sorted_entries = sorted(entries, key=lambda x: x[2 + field_idx], reverse=True)
            top = sorted_entries[0]
            top_val = top[2 + field_idx]
            top_date = date.fromisoformat(top[1])
            is_new = top_date == stats_date
            prev_val, prev_dt = None, None
            if is_new and len(sorted_entries) > 1:
                prev = sorted_entries[1]
                prev_val = prev[2 + field_idx]
                prev_dt = date.fromisoformat(prev[1])
            result.append(UserRecordInfo(
                value=top_val,
                record_date=top_date,
                is_new=is_new,
                prev_value=prev_val,
                prev_date=prev_dt,
                user_id=user_id,
                name=name,
            ))
        result.sort(key=lambda r: r.value, reverse=True)
        return result

    return {
        "chat_msgs":    _build_chat_record(0),
        "chat_length":  _build_chat_record(1),
        "users_msgs":   _build_user_records(0),
        "users_length": _build_user_records(1),
    }
