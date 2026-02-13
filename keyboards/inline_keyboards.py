"""Генерация всех inline-клавиатур."""
from typing import List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class InlineKeyboards:
    """Классы для генерации inline-клавиатур."""

    @staticmethod
    def captcha_button() -> InlineKeyboardMarkup:
        """Капча: одна кнопка «Я человек»."""
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="Я человек", callback_data="captcha:human"))
        return builder.as_markup()

    @staticmethod
    def captcha_math(correct: str, variants: List[str]) -> InlineKeyboardMarkup:
        """Капча: варианты ответа на математический вопрос."""
        builder = InlineKeyboardBuilder()
        for v in variants:
            builder.add(
                InlineKeyboardButton(
                    text=v,
                    callback_data=f"captcha:math:{v}",
                )
            )
        return builder.as_markup()

    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Главное меню пользователя."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="📋 Подать заявку на займ", callback_data="loan:new"),
            InlineKeyboardButton(text="💳 Погасить займ", callback_data="loan:repay_list"),
        )
        builder.row(
            InlineKeyboardButton(text="ℹ️ Информация", callback_data="info:main"),
        )
        return builder.as_markup()

    @staticmethod
    def asset_types() -> InlineKeyboardMarkup:
        """Тип залога: игровой предмет, аккаунт, домен, NFT."""
        builder = InlineKeyboardBuilder()
        for t in ["игровой предмет", "аккаунт", "домен", "NFT"]:
            builder.add(
                InlineKeyboardButton(text=t, callback_data=f"loan_asset:{t}"),
            )
        return builder.as_markup()

    @staticmethod
    def loan_terms() -> InlineKeyboardMarkup:
        """Срок займа: 7, 14, 30 дней."""
        builder = InlineKeyboardBuilder()
        for d in [7, 14, 30]:
            builder.add(
                InlineKeyboardButton(text=f"{d} дней", callback_data=f"loan_term:{d}"),
            )
        return builder.as_markup()

    @staticmethod
    def collateral_sent(loan_id: int) -> InlineKeyboardMarkup:
        """Кнопка «Залог отправлен» после одобрения (с номером займа)."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✅ Залог отправлен", callback_data=f"loan:collateral_sent:{loan_id}"),
        )
        return builder.as_markup()

    @staticmethod
    def admin_main() -> InlineKeyboardMarkup:
        """Главное меню админа."""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📋 Заявки", callback_data="admin:loans"),
        )
        builder.row(
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
        )
        builder.row(
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast"),
            InlineKeyboardButton(text="🔗 Рефералы", callback_data="admin:refs"),
        )
        builder.row(
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin:settings"),
        )
        return builder.as_markup()

    @staticmethod
    def admin_loans_filters() -> InlineKeyboardMarkup:
        """Фильтры заявок: На одобрение / Ожидают залог / Активные / Просроченные / Все."""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="⏳ На одобрение", callback_data="admin_loans:await_approval"),
            InlineKeyboardButton(text="📦 Ожидают залог", callback_data="admin_loans:hold"),
        )
        builder.row(
            InlineKeyboardButton(text="✅ Активные", callback_data="admin_loans:active"),
            InlineKeyboardButton(text="⚠️ Просроченные", callback_data="admin_loans:overdue"),
        )
        builder.row(
            InlineKeyboardButton(text="📄 Все", callback_data="admin_loans:all"),
        )
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back"),
        )
        return builder.as_markup()

    @staticmethod
    def admin_loan_card_await_approval(loan_id: int) -> InlineKeyboardMarkup:
        """Карточка заявки: Одобрить / Отклонить."""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve:{loan_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject:{loan_id}"),
        )
        return builder.as_markup()

    @staticmethod
    def admin_comment_choice(loan_id: int, action: str) -> InlineKeyboardMarkup:
        """Выбор: оставить комментарий или нет. action = 'approve' или 'reject'."""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="💬 С комментарием", callback_data=f"admin_{action}_comment:{loan_id}"),
            InlineKeyboardButton(text="➡️ Без комментария", callback_data=f"admin_{action}_no_comment:{loan_id}"),
        )
        return builder.as_markup()

    @staticmethod
    def admin_loan_card_await_collateral(loan_id: int) -> InlineKeyboardMarkup:
        """Карточка: Залог получен."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✅ Залог получен", callback_data=f"admin_collateral_ok:{loan_id}"),
        )
        return builder.as_markup()

    @staticmethod
    def admin_loan_card_send_loan(loan_id: int) -> InlineKeyboardMarkup:
        """Карточка: Отправить займ (ожидаем ссылку на чек)."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="💰 Отправить займ", callback_data=f"admin_send_loan:{loan_id}"),
        )
        return builder.as_markup()

    @staticmethod
    def admin_loan_card_return_collateral(loan_id: int) -> InlineKeyboardMarkup:
        """Карточка: Залог возвращён."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✅ Залог возвращён", callback_data=f"admin_return_collateral:{loan_id}"),
        )
        return builder.as_markup()

    @staticmethod
    def admin_back() -> InlineKeyboardMarkup:
        """Кнопка «Назад» в админке."""
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="◀ Назад", callback_data="admin:back"))
        return builder.as_markup()

    @staticmethod
    def admin_stats_periods() -> InlineKeyboardMarkup:
        """Статистика: 7 / 30 / 90 дней / всё время."""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="7 дней", callback_data="admin_stats:7"),
            InlineKeyboardButton(text="30 дней", callback_data="admin_stats:30"),
        )
        builder.row(
            InlineKeyboardButton(text="90 дней", callback_data="admin_stats:90"),
            InlineKeyboardButton(text="Всё время", callback_data="admin_stats:all"),
        )
        builder.row(InlineKeyboardButton(text="◀ Назад", callback_data="admin:back"))
        return builder.as_markup()

    @staticmethod
    def admin_broadcast_content_type() -> InlineKeyboardMarkup:
        """Тип контента рассылки: Текст / Фото / Видео."""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="Текст", callback_data="broadcast:text"),
            InlineKeyboardButton(text="Фото", callback_data="broadcast:photo"),
            InlineKeyboardButton(text="Видео", callback_data="broadcast:video"),
        )
        builder.row(InlineKeyboardButton(text="◀ Назад", callback_data="admin:back"))
        return builder.as_markup()

    @staticmethod
    def admin_broadcast_filter() -> InlineKeyboardMarkup:
        """Фильтр получателей: всем / только с активными займами / только просроченные."""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="Всем", callback_data="broadcast_filter:all"),
            InlineKeyboardButton(text="С активными займами", callback_data="broadcast_filter:active"),
        )
        builder.row(
            InlineKeyboardButton(text="Просроченные", callback_data="broadcast_filter:overdue"),
        )
        return builder.as_markup()

    @staticmethod
    def admin_refs_menu() -> InlineKeyboardMarkup:
        """Рефералы: выдать панель, список трафферов."""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="Выдать панель", callback_data="admin_ref:give_panel"),
            InlineKeyboardButton(text="Список трафферов", callback_data="admin_ref:list"),
        )
        builder.row(InlineKeyboardButton(text="◀ Назад", callback_data="admin:back"))
        return builder.as_markup()

    @staticmethod
    def user_active_loans_for_repay(loans: List) -> InlineKeyboardMarkup:
        """Список активных займов для выбора погашения."""
        builder = InlineKeyboardBuilder()
        for loan in loans:
            debt = loan["current_debt"] or 0
            builder.add(
                InlineKeyboardButton(
                    text=f"💳 Займ #{loan['id']} — остаток {debt} USDT",
                    callback_data=f"repay_loan:{loan['id']}",
                )
            )
        builder.row(InlineKeyboardButton(text="◀️ Отмена", callback_data="loan:menu"))
        return builder.as_markup()

    @staticmethod
    def trafer_panel() -> InlineKeyboardMarkup:
        """Панель траффера: Моя рефссылка, История."""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔗 Моя рефссылка", callback_data="trafer:ref_link"),
            InlineKeyboardButton(text="📜 История", callback_data="trafer:history"),
        )
        return builder.as_markup()
