"""Базовый класс для обработчиков."""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot
    from core.database import Database
    from core.config import Config

logger = logging.getLogger(__name__)


class BaseHandler:
    """Базовый класс для обработчиков. Хранит ссылки на bot, db, config."""

    def __init__(
        self,
        bot: "Bot",
        db: "Database",
        config: "Config",
        **kwargs,
    ):
        self.bot = bot
        self.db = db
        self.config = config
        for key, value in kwargs.items():
            setattr(self, key, value)
