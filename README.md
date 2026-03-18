# Chat Bot

Telegram-бот для сбора и отображения статистики сообщений в группе.

## Возможности

- Считает сообщения участников группы
- Показывает статистику за любой период (сегодня, вчера, неделю, месяц, конкретную дату или диапазон)
- Показывает личную статистику пользователя
- Показывает топ дней по сообщениям
- Показывает праздники на сегодня или завтра (через htmlweb.ru)
- Автоматически публикует итоги дня в заданное время

## Команды

Обращаться к боту через `@username`:

```
@bot статистика за сегодня
@bot статистика за вчера
@bot статистика за неделю
@bot статистика за месяц
@bot статистика за всё время
@bot статистика за 12.03
@bot статистика за 12.03.2026
@bot статистика за 01.03-13.03
@bot статистика @username
@bot моя статистика
@bot топ дней
@bot праздник сегодня
@bot праздник завтра
```

## Установка

```bash
git clone https://github.com/slartus/chat_bot.git
cd chat_bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Конфигурация

Создай файл `.env`:

```env
BOT_TOKEN=your_telegram_bot_token
ALLOWED_CHAT_ID=-1001234567890
TIMEZONE=Europe/Moscow
DAILY_STATS_TIME=23:59
```

| Переменная         | Описание                                      | По умолчанию |
|--------------------|-----------------------------------------------|--------------|
| `BOT_TOKEN`        | Токен бота от @BotFather                      | обязательно  |
| `ALLOWED_CHAT_ID`  | ID группы, в которой работает бот             | обязательно  |
| `TIMEZONE`         | Часовой пояс                                  | `UTC`        |
| `DAILY_STATS_TIME` | Время ежедневной сводки в формате `HH:MM`     | `23:59`      |
| `ADMIN_USER_ID`    | Telegram user ID для еженедельного бэкапа БД  | не задано    |

## Запуск

```bash
python bot.py
```

### Через systemd

```ini
[Unit]
Description=Telegram Chat Bot
After=network.target

[Service]
WorkingDirectory=/opt/chat_bot
ExecStart=/opt/chat_bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
