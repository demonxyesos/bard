"""Админ-панель: только кнопки, без текстовых команд."""
import logging
import secrets
from datetime import datetime
from typing import Optional
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.config import Config
from keyboards.inline_keyboards import InlineKeyboards
from handlers.base_handler import BaseHandler
from services.finance_service import FinanceService
from utils.validators import validate_amount, validate_days, validate_invoice_link
from utils.markdown import escape_markdown_v2

logger = logging.getLogger(__name__)


class AdminStates(StatesGroup):
    approve_amount = State()
    approve_comment = State()
    reject_comment = State()
    invoice_link = State()
    broadcast_content_type = State()
    broadcast_text = State()
    broadcast_photo = State()
    broadcast_video = State()
    broadcast_caption = State()
    broadcast_time = State()
    broadcast_filter = State()
    trafer_tariff_fixed = State()
    trafer_tariff_percent = State()
    user_search = State()


def _loan_card_text(loan, username: str = "") -> str:
    """Текст карточки заявки. loan — Row из БД."""
    u = username or f"id{loan['user_id']}"
    adesc = loan["asset_description"] or ""
    desc = adesc[:200] + "..." if len(adesc) > 200 else (adesc or "-")
    return (
        f"Займ #{loan['id']}\n"
        f"Пользователь: @{u}\n"
        f"Тип актива: {loan['asset_type']}\n"
        f"Описание: {desc}\n"
        f"Запрошено: {loan['requested_amount']} USDT\n"
        f"Статус: {loan['status']}"
    )


class AdminHandler(BaseHandler):
    """Обработчики админ-панели."""

    def __init__(self, *args, finance_service: FinanceService = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.finance = finance_service or FinanceService(Config.INTEREST_RATE, Config.PENALTY_RATE)
        self.router = Router(name="admin")

    def register(self) -> None:
        self.router.message.register(self.cmd_admin, Command("админ"))
        self.router.message.register(self.cmd_admin, Command("admin"))
        # Специфичные callback-и ПЕРЕД общим admin_callback, иначе admin_approve:1 перехватывается admin
        self.router.callback_query.register(self.admin_approve_comment_choice, F.data.startswith("admin_approve_comment:"))
        self.router.callback_query.register(self.admin_approve_no_comment, F.data.startswith("admin_approve_no_comment:"))
        self.router.callback_query.register(self.admin_reject_comment_choice, F.data.startswith("admin_reject_comment:"))
        self.router.callback_query.register(self.admin_reject_no_comment, F.data.startswith("admin_reject_no_comment:"))
        self.router.callback_query.register(self.admin_approve_callback, F.data.startswith("admin_approve:"))
        self.router.callback_query.register(self.admin_reject_callback, F.data.startswith("admin_reject:"))
        self.router.callback_query.register(self.admin_loans_callback, F.data.startswith("admin_loans"))
        self.router.callback_query.register(self.admin_collateral_ok_callback, F.data.startswith("admin_collateral_ok:"))
        self.router.callback_query.register(self.admin_return_collateral_callback, F.data.startswith("admin_return_collateral:"))
        self.router.callback_query.register(self.admin_stats_callback, F.data.startswith("admin_stats:"))
        self.router.callback_query.register(self.admin_ref_callback, F.data.startswith("admin_ref"))
        self.router.callback_query.register(self.admin_broadcast_callback, F.data.startswith("broadcast"))
        self.router.callback_query.register(self.admin_callback, F.data.startswith("admin"))
        self.router.message.register(self.admin_approve_amount_input, AdminStates.approve_amount)
        self.router.message.register(self.admin_approve_comment_input, AdminStates.approve_comment)
        self.router.message.register(self.admin_reject_comment_input, AdminStates.reject_comment)
        self.router.message.register(self.admin_invoice_link_input, AdminStates.invoice_link)
        self.router.message.register(self.admin_broadcast_text_input, AdminStates.broadcast_text)
        self.router.message.register(self.admin_broadcast_photo_input, AdminStates.broadcast_photo)
        self.router.message.register(self.admin_broadcast_video_input, AdminStates.broadcast_video)
        self.router.message.register(self.admin_broadcast_caption_input, AdminStates.broadcast_caption)
        self.router.message.register(self.admin_broadcast_time_input, AdminStates.broadcast_time)
        self.router.message.register(self.admin_user_search_input, AdminStates.user_search)
        self.router.message.register(self.admin_trafer_tariff_input, AdminStates.trafer_tariff_percent)

    def _admin_only(self, user_id: int) -> bool:
        return Config.is_admin(user_id)

    async def cmd_admin(self, message: Message, state: FSMContext) -> None:
        if not message.from_user or not self._admin_only(message.from_user.id):
            await message.answer("🚫 Доступ запрещён.")
            return
        await state.clear()
        await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=InlineKeyboards.admin_main())

    async def admin_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            await callback.answer("Доступ запрещён.")
            return
        data = callback.data
        if data == "admin:back":
            await callback.message.edit_text("⚙️ <b>Админ-панель</b>", reply_markup=InlineKeyboards.admin_main())
        elif data == "admin:loans":
            await callback.message.edit_text("📋 Заявки — выберите фильтр:", reply_markup=InlineKeyboards.admin_loans_filters())
        elif data == "admin:users":
            await callback.message.edit_text("👥 Введите ID или username для поиска (или 0 для списка):")
            await state.set_state(AdminStates.user_search)
            await state.update_data(admin_ref_give_panel=False)
        elif data == "admin:stats":
            await callback.message.edit_text("📊 Статистика — выберите период:", reply_markup=InlineKeyboards.admin_stats_periods())
        elif data == "admin:broadcast":
            await state.set_state(AdminStates.broadcast_content_type)
            await callback.message.edit_text("📢 Тип контента рассылки:", reply_markup=InlineKeyboards.admin_broadcast_content_type())
        elif data == "admin:refs":
            await callback.message.edit_text("🔗 Рефералы:", reply_markup=InlineKeyboards.admin_refs_menu())
        elif data == "admin:settings":
            await callback.message.edit_text(
                f"⚙️ <b>Настройки</b>\n\n📈 Процент в день: {Config.INTEREST_RATE*100}%\n💰 Штраф: {Config.PENALTY_RATE*100}%\n\n(изменение в core/config.py)"
            )
        await callback.answer()

    async def admin_loans_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            await callback.answer("Доступ запрещён.")
            return
        _, filter_type = callback.data.split(":", 1)
        if filter_type == "await_approval":
            loans = await self.db.get_loans_awaiting_approval()
        elif filter_type == "hold":
            loans = await self.db.get_loans_in_hold()
        elif filter_type == "active":
            loans = await self.db.get_active_loans()
        elif filter_type == "overdue":
            loans = await self.db.get_overdue_loans()
        else:
            loans = await self.db.get_all_loans()
        if not loans:
            await callback.message.edit_text("📭 Нет заявок по выбранному фильтру.", reply_markup=InlineKeyboards.admin_loans_filters())
            await callback.answer()
            return
        await callback.message.edit_text(f"📋 Найдено заявок: <b>{len(loans)}</b>. Ниже карточки.")
        for loan in loans:
            user = await self.db.get_user(loan["user_id"])
            username = (user["username"] or "").strip() or f"id{loan['user_id']}"
            adesc = loan["asset_description"] or ""
            desc = adesc[:200]
            if len(adesc) > 200:
                desc = desc + "..."
            text = (
                f"📄 <b>Займ #{loan['id']}</b> | @{username}\n"
                f"📦 Тип: {loan['asset_type']} | 💰 {loan['requested_amount']} USDT\n"
                f"📝 {desc}\n\n🔄 Статус: {loan['status']}"
            )
            status = loan["status"]
            if status == "ожидает_одобрения":
                kb = InlineKeyboards.admin_loan_card_await_approval(loan["id"])
            elif status == "ожидает_залог":
                kb = InlineKeyboards.admin_loan_card_await_collateral(loan["id"])
            elif status == "погашен":
                kb = InlineKeyboards.admin_loan_card_return_collateral(loan["id"])
            else:
                kb = InlineKeyboards.admin_back()
            await callback.message.answer(text, reply_markup=kb)
        await callback.message.answer("◀️ Назад", reply_markup=InlineKeyboards.admin_loans_filters())
        await callback.answer()

    async def admin_approve_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            return
        try:
            loan_id = int(callback.data.split(":")[-1])
        except (ValueError, IndexError):
            return
        await state.update_data(admin_pending_loan_id=loan_id)
        await state.set_state(AdminStates.approve_amount)
        await callback.message.answer("💰 Введите сумму займа в USDT (например: 420):")

    async def admin_approve_amount_input(self, message: Message, state: FSMContext) -> None:
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        ok, amount, err = validate_amount(message.text or "")
        if not ok:
            await message.answer(f"❌ {err}")
            return
        data = await state.get_data()
        loan_id = data.get("admin_pending_loan_id")
        if not loan_id:
            await state.clear()
            await message.answer("⏰ Сессия истекла.")
            return
        await state.update_data(admin_approve_amount=amount)
        await state.set_state(AdminStates.approve_comment)
        await message.answer("💬 Хотите оставить комментарий пользователю?", reply_markup=InlineKeyboards.admin_comment_choice(loan_id, "approve"))

    async def admin_approve_comment_choice(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Админ выбрал «С комментарием» при одобрении."""
        await callback.answer()
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            return
        try:
            loan_id = int(callback.data.split(":")[-1])
        except (ValueError, IndexError):
            return
        await state.update_data(admin_pending_loan_id=loan_id)
        await state.set_state(AdminStates.approve_comment)
        await callback.message.edit_text("💬 Введите комментарий для пользователя:")

    async def admin_approve_no_comment(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Админ выбрал «Без комментария» при одобрении."""
        await callback.answer()
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            return
        try:
            loan_id = int(callback.data.split(":")[-1])
        except (ValueError, IndexError):
            return
        data = await state.get_data()
        amount = data.get("admin_approve_amount")
        if not amount:
            await callback.message.answer("❌ Ошибка: сумма не найдена. Начните одобрение заново.")
            await state.clear()
            return
        await self._do_approve_loan(loan_id, state, comment=None, admin_message=callback.message)

    async def admin_approve_comment_input(self, message: Message, state: FSMContext) -> None:
        """Ввод комментария при одобрении."""
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        comment = (message.text or "").strip()
        if not comment:
            await message.answer("❌ Комментарий не может быть пустым. Введите комментарий или отправьте /отмена для отмены.")
            return
        data = await state.get_data()
        loan_id = data.get("admin_pending_loan_id")
        if not loan_id:
            await state.clear()
            await message.answer("⏰ Сессия истекла.")
            return
        await self._do_approve_loan(loan_id, state, comment=comment, admin_message=message)

    async def _do_approve_loan(self, loan_id: int, state: FSMContext, comment: Optional[str] = None, admin_message: Optional[Message] = None) -> None:
        """Выполнить одобрение займа с комментарием или без."""
        data = await state.get_data()
        amount = data.get("admin_approve_amount")
        if not amount:
            await state.clear()
            return
        await self.db.approve_loan(loan_id, amount)
        loan = await self.db.get_loan(loan_id)
        await state.clear()
        user_msg = f"✅ <b>Заявка #{loan_id} одобрена</b> на сумму {amount} USDT."
        if comment:
            user_msg += f"\n\n💬 Комментарий администратора:\n{comment}"
        user_msg += "\n\nОтправьте залог по инструкции и нажмите кнопку ниже 👇"
        try:
            await self.bot.send_message(
                loan["user_id"],
                user_msg,
                reply_markup=InlineKeyboards.collateral_sent(loan_id),
            )
        except Exception as e:
            logger.warning("Notify user %s: %s", loan["user_id"], e)
        admin_msg = f"✅ Займ #{loan_id} одобрен на сумму <b>{amount} USDT</b>."
        if comment:
            admin_msg += f"\n💬 Комментарий отправлен пользователю."
        if admin_message:
            await admin_message.answer(admin_msg)

    async def admin_reject_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            return
        try:
            loan_id = int(callback.data.split(":")[-1])
        except (ValueError, IndexError):
            return
        await state.update_data(admin_pending_reject_loan_id=loan_id)
        await callback.message.answer("💬 Хотите оставить комментарий пользователю?", reply_markup=InlineKeyboards.admin_comment_choice(loan_id, "reject"))

    async def admin_reject_comment_choice(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Админ выбрал «С комментарием» при отклонении."""
        await callback.answer()
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            return
        try:
            loan_id = int(callback.data.split(":")[-1])
        except (ValueError, IndexError):
            return
        await state.update_data(admin_pending_loan_id=loan_id)
        await state.set_state(AdminStates.reject_comment)
        await callback.message.edit_text("💬 Введите комментарий для пользователя:")

    async def admin_reject_no_comment(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Админ выбрал «Без комментария» при отклонении."""
        await callback.answer()
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            return
        try:
            loan_id = int(callback.data.split(":")[-1])
        except (ValueError, IndexError):
            return
        await self._do_reject_loan(loan_id, comment=None, admin_message=callback.message)

    async def admin_reject_comment_input(self, message: Message, state: FSMContext) -> None:
        """Ввод комментария при отклонении."""
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        comment = (message.text or "").strip()
        if not comment:
            await message.answer("❌ Комментарий не может быть пустым. Введите комментарий или отправьте /отмена для отмены.")
            return
        data = await state.get_data()
        loan_id = data.get("admin_pending_loan_id")
        if not loan_id:
            await state.clear()
            await message.answer("⏰ Сессия истекла.")
            return
        await self._do_reject_loan(loan_id, comment=comment, admin_message=message)
        await state.clear()

    async def _do_reject_loan(self, loan_id: int, comment: Optional[str] = None, admin_message: Optional[Message] = None) -> None:
        """Выполнить отклонение займа с комментарием или без."""
        await self.db.reject_loan(loan_id)
        loan = await self.db.get_loan(loan_id)
        user_msg = f"❌ Заявка #{loan_id} отклонена."
        if comment:
            user_msg += f"\n\n💬 Комментарий администратора:\n{comment}"
        try:
            await self.bot.send_message(loan["user_id"], user_msg)
        except Exception:
            pass
        admin_msg = f"❌ Заявка #{loan_id} отклонена."
        if comment:
            admin_msg += f"\n💬 Комментарий отправлен пользователю."
        if admin_message:
            await admin_message.answer(admin_msg)

    async def admin_collateral_ok_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            return
        try:
            loan_id = int(callback.data.split(":")[-1])
        except (ValueError, IndexError):
            return
        loan = await self.db.get_loan(loan_id)
        if not loan or loan["status"] != "ожидает_залог":
            await callback.message.answer("❌ Займ не в статусе ожидания залога или уже обработан.")
            return
        await state.update_data(admin_pending_invoice_loan_id=loan_id)
        await state.set_state(AdminStates.invoice_link)
        await callback.message.answer("🔗 Отправьте ссылку на чек из @CryptoBot:\n<code>https://t.me/CryptoBot?start=invoice_xxx</code>")

    async def admin_invoice_link_input(self, message: Message, state: FSMContext) -> None:
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        ok, link, err = validate_invoice_link(message.text or "")
        if not ok:
            await message.answer(err)
            return
        data = await state.get_data()
        loan_id = data.get("admin_pending_invoice_loan_id")
        if not loan_id:
            await state.clear()
            return
        loan = await self.db.get_loan(loan_id)
        if not loan:
            await state.clear()
            return
        principal = loan["approved_amount"] or loan["requested_amount"]
        term_days = loan["hold_days"] or 14  # Используем срок из заявки (бывший hold_days теперь просто срок займа)
        total_debt = self.finance.calculate_total_debt(principal, term_days, loan["interest_rate"] if loan["interest_rate"] is not None else None)
        due_date = self.finance.calculate_due_date(datetime.utcnow(), term_days)
        await self.db.set_loan_active(loan_id, link, due_date, total_debt)
        await state.clear()
        await message.answer(f"✅ Займ #{loan_id} выдан. Долг: <b>{total_debt} USDT</b>, погашение до {due_date.date()}.")
        try:
            await self.bot.send_message(
                loan["user_id"],
                f"💰 <b>Займ #{loan_id} выдан</b>\n\n"
                f"Администратор перевёл вам <b>{loan['approved_amount'] or loan['requested_amount']} USDT</b> за ваш залог.\n\n"
                f"📌 Сумма к погашению: <b>{total_debt} USDT</b>\n"
                f"📅 Срок погашения: до {due_date.date()}\n\n"
                f"Для погашения используйте кнопку «💳 Погасить займ» в главном меню.",
            )
        except Exception as e:
            logger.warning("Notify user: %s", e)

    async def admin_return_collateral_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        loan_id = int(callback.data.split(":")[-1])
        await self.db.set_loan_completed(loan_id)
        await callback.answer("✅ Залог возвращён, сделка завершена.")

    async def admin_stats_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            await callback.answer("Доступ запрещён.")
            return
        _, period = callback.data.split(":", 1)
        days = None if period == "all" else int(period)
        stats = await self.db.get_stats(days)
        text = (
            f"📊 <b>Статистика</b> ({period} дн. / всё время)\n\n"
            f"📋 Заявок: {stats['total_loans']}\n"
            f"✅ Выдано займов: {stats['issued_count']}\n"
            f"💰 Сумма выданных: <b>{stats['issued_sum']} USDT</b>"
        )
        await callback.message.edit_text(text, reply_markup=InlineKeyboards.admin_stats_periods())
        await callback.answer()

    async def admin_broadcast_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            await callback.answer("Доступ запрещён.")
            return
        if callback.data.startswith("broadcast:"):
            content_type = callback.data.replace("broadcast:", "")
            await state.update_data(broadcast_content_type=content_type)
            if content_type == "text":
                await state.set_state(AdminStates.broadcast_text)
                await callback.message.answer("📝 Введите текст рассылки (MarkdownV2):")
            elif content_type == "photo":
                await state.set_state(AdminStates.broadcast_photo)
                await callback.message.answer("📷 Отправьте фото:")
            elif content_type == "video":
                await state.set_state(AdminStates.broadcast_video)
                await callback.message.answer("🎬 Отправьте видео:")
        elif callback.data.startswith("broadcast_filter:"):
            filter_type = callback.data.replace("broadcast_filter:", "")
            await state.update_data(broadcast_filter=filter_type)
            await state.set_state(AdminStates.broadcast_time)
            await callback.message.answer("🕐 Введите время отправки: <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>\n(например: 05.02.2026 14:00)")
        await callback.answer()

    async def admin_broadcast_text_input(self, message: Message, state: FSMContext) -> None:
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        text = message.text or ""
        await state.update_data(broadcast_content=text, broadcast_parse_mode="MarkdownV2")
        await state.set_state(AdminStates.broadcast_filter)
        await message.answer("👥 Выберите получателей:", reply_markup=InlineKeyboards.admin_broadcast_filter())

    async def admin_broadcast_photo_input(self, message: Message, state: FSMContext) -> None:
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        if not message.photo:
            await message.answer("❌ Отправьте фото.")
            return
        file_id = message.photo[-1].file_id
        await state.update_data(broadcast_content=file_id, broadcast_content_type="photo")
        await state.set_state(AdminStates.broadcast_caption)
        await message.answer("📝 Введите подпись к фото (MarkdownV2):")

    async def admin_broadcast_video_input(self, message: Message, state: FSMContext) -> None:
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        if not message.video:
            await message.answer("❌ Отправьте видео.")
            return
        file_id = message.video.file_id
        await state.update_data(broadcast_content=file_id, broadcast_content_type="video")
        await state.set_state(AdminStates.broadcast_caption)
        await message.answer("📝 Введите подпись к видео (MarkdownV2):")

    async def admin_broadcast_caption_input(self, message: Message, state: FSMContext) -> None:
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        caption = message.text or ""
        await state.update_data(broadcast_caption=caption, broadcast_parse_mode="MarkdownV2")
        await state.set_state(AdminStates.broadcast_filter)
        await message.answer("👥 Выберите получателей:", reply_markup=InlineKeyboards.admin_broadcast_filter())

    async def admin_broadcast_time_input(self, message: Message, state: FSMContext) -> None:
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            dt = datetime.strptime(raw, "%d.%m.%Y %H:%M")
        except ValueError:
            await message.answer("Неверный формат. Используйте ДД.ММ.ГГГГ ЧЧ:ММ")
            return
        data = await state.get_data()
        content_type = data.get("broadcast_content_type", "text")
        content = data.get("broadcast_content", "")
        caption = data.get("broadcast_caption", "")
        parse_mode = data.get("broadcast_parse_mode", "MarkdownV2")
        filter_type = data.get("broadcast_filter", "all")
        await self.db.create_broadcast(
            content_type=content_type,
            send_time=dt,
            content=content,
            caption=caption,
            parse_mode=parse_mode,
            filter_type=filter_type,
        )
        await state.clear()
        await message.answer(f"✅ Рассылка запланирована на <b>{dt.strftime('%d.%m.%Y %H:%M')}</b>.")
        await message.answer("⚙️ Админ-панель:", reply_markup=InlineKeyboards.admin_main())

    async def admin_ref_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.from_user or not self._admin_only(callback.from_user.id):
            await callback.answer("Доступ запрещён.")
            return
        if callback.data == "admin_ref:give_panel":
            users = await self.db.get_all_users()
            if not users:
                await callback.message.answer("Нет пользователей.")
                await callback.answer()
                return
            list_text = "\n".join([f"ID {u['id']} @{u['username'] or '-'}" for u in users[:50]])
            await callback.message.answer(f"👤 Введите ID пользователя для выдачи панели траффера:\n\n{list_text}")
            await state.set_state(AdminStates.user_search)
            await state.update_data(admin_ref_give_panel=True)
        elif callback.data == "admin_ref:list":
            trafers = await self.db.get_all_trafers()
            if not trafers:
                await callback.message.answer("📭 Нет трафферов.")
            else:
                text = "\n".join([f"👤 ID {t['user_id']} | token: {t['panel_token'][:8]}... | фикс {t['fixed_rate']} + {t['percent_rate']}%" for t in trafers])
                await callback.message.answer(text or "Список пуст.")
        await callback.answer()

    async def admin_user_search_input(self, message: Message, state: FSMContext) -> None:
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        data = await state.get_data()
        give_panel = data.get("admin_ref_give_panel")
        text = (message.text or "").strip()
        if give_panel:
            try:
                user_id = int(text)
            except ValueError:
                await message.answer("Введите числовой ID пользователя.")
                return
            existing = await self.db.get_trafer_by_user_id(user_id)
            if existing:
                await message.answer(f"У пользователя {user_id} уже есть панель. Токен: {existing['panel_token'][:12]}...")
                await state.clear()
                await message.answer("Админ-панель:", reply_markup=InlineKeyboards.admin_main())
                return
            token = secrets.token_urlsafe(24)
            await self.db.create_trafer(user_id, token)
            bot_info = await self.bot.get_me()
            username = bot_info.username if bot_info else "bot"
            link = f"https://t.me/{username}?start=panel_{token}"
            await message.answer(f"✅ Панель выдана.\n\n🔗 Ссылка для траффера:\n{link}")
            await state.clear()
            await message.answer("⚙️ Админ-панель:", reply_markup=InlineKeyboards.admin_main())
            return
        if text == "0" or not text:
            users = await self.db.get_all_users()
        else:
            users = await self.db.search_users(text)
        if not users:
            await message.answer("📭 Пользователи не найдены.")
            return
        lines = [f"👤 ID {u['id']} | @{u['username'] or '-'} | {'🚫' if u['is_blocked'] else '✅'}" for u in users[:30]]
        await message.answer("\n".join(lines))
        await state.clear()
        await message.answer("⚙️ Админ-панель:", reply_markup=InlineKeyboards.admin_main())

    async def admin_trafer_tariff_input(self, message: Message, state: FSMContext) -> None:
        if not message.from_user or not self._admin_only(message.from_user.id):
            return
        await state.clear()
        await message.answer("Тариф изменён (используйте кнопки в Рефералы для выбора траффера).")
