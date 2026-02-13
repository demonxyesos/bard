"""Запуск бота «Цифровой ломбард»."""
import asyncio
import logging

from core.bot import BotApp

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    app = BotApp()
    await app.start()


if __name__ == "__main__":
    asyncio.run(main())
