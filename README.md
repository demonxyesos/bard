# Telegram-бот «Цифровой ломбард»

Микрокредитование под залог цифровых активов (игровые предметы, аккаунты, домены, NFT) без верификации личности. Операции в криптовалюте (USDT, TON, BTC) через @CryptoBot.

## Требования

- Python 3.12
- Токен бота (BotFather)
- API-токен @CryptoBot (Merchant → API Token)

## Установка

```bash
pip install -r requirements.txt
# Отредактируйте core/config.py: BOT_TOKEN, CRYPTO_API_KEY, ADMIN_IDS
```

## Запуск

```bash
python main.py
```

Бот работает в режиме polling (без вебхуков). При первом запуске создаётся база `bot.db` и таблицы. Резервные копии БД сохраняются каждые 6 часов в папку `backups/`. Логи — в `logs/app.log`.

## Команды

- **Пользователь:** `/start` — капча, затем главное меню (Подать заявку / Погасить займ).
- **Админ:** `/админ` — панель (доступ только для ID из `ADMIN_IDS`).
- **Траффер:** ссылка `https://t.me/<bot>?start=panel_<token>` — панель траффера (токен выдаёт админ в разделе Рефералы).

## Структура проекта

- `core/` — BotApp, Config, Database, Scheduler
- `services/` — CryptoService, FinanceService, CaptchaService
- `models/` — User, Loan, Trafer
- `handlers/` — UserHandler, AdminHandler, TraferHandler
- `keyboards/` — InlineKeyboards, ReplyKeyboards
- `utils/` — markdown, validators

Все тексты бота на русском языке.
