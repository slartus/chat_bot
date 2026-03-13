import aiosqlite
from datetime import date

DB_PATH = "messages.db"
SCHEMA_VERSION = 2


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
) -> tuple[int, list[tuple[str, int, int]]]:
    """Возвращает (total_msgs, [(display_name, count, total_length), ...])."""
    cond, params = _date_condition(date_from, date_to)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"""
            SELECT
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

    total = sum(cnt for _, cnt, _ in rows)
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
