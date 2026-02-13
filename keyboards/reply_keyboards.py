"""Обычные (reply) клавиатуры."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


class ReplyKeyboards:
    """Классы для генерации reply-клавиатур."""

    @staticmethod
    def remove() -> ReplyKeyboardMarkup:
        """Убрать клавиатуру (для удаления после выбора)."""
        return ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            remove_keyboard=True,
        )

    @staticmethod
    def admin_remove() -> ReplyKeyboardMarkup:
        """Убрать клавиатуру в админке."""
        return ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            remove_keyboard=True,
        )
