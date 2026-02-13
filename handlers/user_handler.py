"""Обработчики команд пользователей: /start, капча, заявка, погашение."""
import logging
from datetime import datetime
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.config import Config
from keyboards.inline_keyboards import InlineKeyboards
from keyboards.reply_keyboards import ReplyKeyboards
from handlers.base_handler import BaseHandler
from services.captcha_service import CaptchaService
from services.finance_service import FinanceService
from services.crypto_service import CryptoService
from utils.validators import validate_amount

logger = logging.getLogger(__name__)

LEGAL_WARNING = (
    "⚠️ Услуга без KYC. Вы несёте ответственность за легальность передаваемого актива."
)


class LoanApplicationStates(StatesGroup):
    asset_type = State()
    description = State()
    amount = State()
    term_days = State()
    proof = State()


class RepayStates(StatesGroup):
    choose_loan = State()
    amount = State()


def get_ref_id_from_start(payload: str) -> tuple:
    """Из start=ref_XXX или start=panel_XXX возвращает (ref_id, is_panel). ref_id = 0 если не реф."""
    if not payload:
        return Config.DEFAULT_REF_ID, False
    if payload.startswith("ref_"):
        try:
            return int(payload.replace("ref_", "")), False
        except ValueError:
            return Config.DEFAULT_REF_ID, False
    if payload.startswith("panel_"):
        return 0, True  # траффер панель — обрабатывается в trafer_handler
    try:
        return int(payload), False
    except ValueError:
        return Config.DEFAULT_REF_ID, False


class UserHandler(BaseHandler):
    """Обработчики пользователей."""

    def __init__(self, *args, captcha_service: CaptchaService = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.captcha = captcha_service or CaptchaService()
        self.finance = getattr(self, "finance_service", None) or FinanceService(
            Config.INTEREST_RATE, Config.PENALTY_RATE
        )
        self.crypto = getattr(self, "crypto_service", None)
        self.router = Router(name="user")

    def register(self) -> None:
        self.router.message.register(self.cmd_start, CommandStart())
        self.router.callback_query.register(self.captcha_callback, F.data.startswith("captcha:"))
        # Специфичные loan callback-и ПЕРЕД общим main_menu_callback
        self.router.callback_query.register(self.collateral_sent_callback, F.data.startswith("loan:collateral_sent"))
        self.router.callback_query.register(self.loan_asset_callback, F.data.startswith("loan_asset:"))
        self.router.callback_query.register(self.loan_term_callback, F.data.startswith("loan_term:"))
        self.router.callback_query.register(self.repay_loan_callback, F.data.startswith("repay_loan:"))
        self.router.callback_query.register(self.info_callback, F.data.startswith("info:"))
        self.router.callback_query.register(self.main_menu_callback, F.data.startswith("loan:"))
        self.router.message.register(self.loan_application_description, LoanApplicationStates.description)
        self.router.message.register(self.loan_application_amount, LoanApplicationStates.amount)
        self.router.message.register(self.loan_application_term, LoanApplicationStates.term_days)
        self.router.message.register(self.loan_application_proof, LoanApplicationStates.proof)
        self.router.message.register(self.repay_amount_input, RepayStates.amount)

    async def cmd_start(self, message: Message, state: FSMContext) -> None:
        """Команда /start. Показать капчу. Реферал из start=ref_XXX."""
        await state.clear()
        payload = message.text and message.text.split(maxsplit=1)[-1].strip() or ""
        ref_id, is_panel = get_ref_id_from_start(payload)
        if is_panel:
            # Панель траффера — переадресация в trafer_handler по callback
            return
        user = await self.db.get_user(message.from_user.id) if message.from_user else None
        if user:
            if message.from_user and message.from_user.username != (user["username"] or ""):
                await self.db.update_user_username(message.from_user.id, message.from_user.username)
            if user["is_blocked"]:
                await message.answer("🚫 Вы заблокированы.")
                return
            await self._show_main_menu(message, state)
            return
        # Капча
        text, correct, variants = self.captcha.generate()
        await state.update_data(captcha_correct=correct, ref_id=ref_id)
        if correct == "human":
            kb = InlineKeyboards.captcha_button()
        else:
            kb = InlineKeyboards.captcha_math(correct, variants)
        await message.answer(text, reply_markup=kb)

    async def captcha_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Проверка капчи и создание пользователя."""
        data = await state.get_data()
        correct = data.get("captcha_correct")
        ref_id = data.get("ref_id", Config.DEFAULT_REF_ID)
        if not correct:
            await callback.answer("Ошибка. Нажмите /start снова.")
            return
        payload = callback.data
        if ":" in payload:
            _, _, answer = payload.split(":", 2)
        else:
            answer = "human"
        if answer != correct:
            await callback.answer("Неверно. Попробуйте снова.")
            return
        user_id = callback.from_user.id if callback.from_user else 0
        username = callback.from_user.username if callback.from_user else None
        trafer_id = None
        if ref_id and ref_id != Config.DEFAULT_REF_ID:
            trafer = await self.db.get_trafer_by_user_id(ref_id)
            if trafer:
                trafer_id = trafer["id"]
        await self.db.create_user(user_id, username, ref_id, trafer_id)
        await state.clear()
        await callback.message.edit_text(
            f"{LEGAL_WARNING}\n\n🏠 <b>Главное меню</b>"
        )
        await callback.message.answer("👇 Выберите действие:", reply_markup=InlineKeyboards.main_menu())
        await callback.answer()

    async def _show_main_menu(self, message: Message, state: FSMContext) -> None:
        """Показать главное меню (для уже зарегистрированных)."""
        await state.clear()
        user = await self.db.get_user(message.from_user.id) if message.from_user else None
        if user and user["is_blocked"]:
            await message.answer("Вы заблокированы.")
            return
        await message.answer("👇 Выберите действие:", reply_markup=InlineKeyboards.main_menu())

    async def main_menu_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Главное меню: Подать заявку / Погасить займ."""
        if callback.data == "loan:new":
            await state.set_state(LoanApplicationStates.asset_type)
            await state.update_data(loan_application={})
            await callback.message.edit_text("📦 Выберите тип залога:", reply_markup=InlineKeyboards.asset_types())
        elif callback.data == "loan:repay_list":
            user_id = callback.from_user.id if callback.from_user else 0
            loans = await self.db.get_user_active_loans(user_id)
            if not loans:
                await callback.answer("Нет активных займов для погашения.")
                return
            await state.set_state(RepayStates.choose_loan)
            await state.update_data(repay_loan_ids=[l["id"] for l in loans])
            await callback.message.edit_text(
                "💳 Выберите займ для погашения:",
                reply_markup=InlineKeyboards.user_active_loans_for_repay(loans),
            )
        elif callback.data == "loan:menu":
            await state.clear()
            await callback.message.edit_text("🏠 <b>Главное меню</b>")
            await callback.message.answer("👇 Выберите действие:", reply_markup=InlineKeyboards.main_menu())
        await callback.answer()

    async def loan_asset_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Выбор типа актива."""
        asset = callback.data.replace("loan_asset:", "")
        await state.update_data(loan_application={"asset_type": asset})
        await state.set_state(LoanApplicationStates.description)
        await callback.message.edit_text("📝 Опишите актив подробно (текстом):")
        await callback.answer()

    async def loan_term_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Выбор срока займа."""
        term = int(callback.data.replace("loan_term:", ""))
        data = await state.get_data()
        app = data.get("loan_application") or {}
        app["term_days"] = term
        await state.update_data(loan_application=app)
        await state.set_state(LoanApplicationStates.proof)
        await callback.message.edit_text("📎 Загрузите скриншот или видео как доказательство владения активом:")
        await callback.answer()

    async def loan_application_description(self, message: Message, state: FSMContext) -> None:
        """Описание актива."""
        text = (message.text or "").strip()
        if not text:
            await message.answer("❌ Введите описание текстом.")
            return
        data = await state.get_data()
        app = data.get("loan_application") or {}
        app["description"] = text
        await state.update_data(loan_application=app)
        await state.set_state(LoanApplicationStates.amount)
        await message.answer("💰 Введите желаемую сумму займа в USDT (число):")

    async def loan_application_amount(self, message: Message, state: FSMContext) -> None:
        """Сумма займа."""
        ok, val, err = validate_amount(message.text or "", min_val=0.1)
        if not ok:
            await message.answer(f"❌ {err}")
            return
        data = await state.get_data()
        app = data.get("loan_application") or {}
        app["amount"] = val
        await state.update_data(loan_application=app)
        await state.set_state(LoanApplicationStates.term_days)
        await message.answer("⏱ Выберите срок займа:", reply_markup=InlineKeyboards.loan_terms())

    async def loan_application_term(self, message: Message, state: FSMContext) -> None:
        """Срок — только через кнопки."""
        await message.answer("👆 Выберите срок кнопкой выше (7, 14 или 30 дней).")

    async def loan_application_proof(self, message: Message, state: FSMContext) -> None:
        """Доказательство: фото или видео. file_id сохраняем."""
        file_id = None
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.video:
            file_id = message.video.file_id
        if not file_id:
            await message.answer("❌ Отправьте фото или видео.")
            return
        data = await state.get_data()
        app = data.get("loan_application") or {}
        user_id = message.from_user.id if message.from_user else 0
        asset_type = app.get("asset_type", "")
        description = app.get("description", "")
        amount = app.get("amount", 0)
        term_days = app.get("term_days", 7)
        loan_id = await self.db.create_loan(
            user_id=user_id,
            asset_type=asset_type,
            asset_description=description,
            asset_proof=file_id,
            requested_amount=amount,
            hold_days=term_days,
            interest_rate=Config.INTEREST_RATE,
        )
        await state.clear()
        await message.answer(
            f"✅ <b>Заявка #{loan_id} принята.</b>\n\nОжидайте решения администратора."
        )
        await message.answer("🏠 Главное меню:", reply_markup=InlineKeyboards.main_menu())
        # Уведомить админов о новой заявке
        loan = await self.db.get_loan(loan_id)
        user = await self.db.get_user(user_id)
        username = (user["username"] or "").strip() if user else f"id{user_id}"
        if not username:
            username = f"id{user_id}"
        adesc = loan["asset_description"] or ""
        desc = adesc[:300]
        if len(adesc) > 300:
            desc = desc + "..."
        admin_text = (
            f"📋 <b>Новая заявка на займ #{loan_id}</b>\n\n"
            f"👤 Пользователь: @{username}\n"
            f"📦 Тип актива: {loan['asset_type']}\n"
            f"💰 Запрошено: {loan['requested_amount']} USDT\n"
            f"⏱ Срок: {loan['hold_days']} дн.\n\n"
            f"📝 Описание:\n{desc}"
        )
        if len(admin_text) > 1024:
            admin_text = admin_text[:1021] + "..."
        kb = InlineKeyboards.admin_loan_card_await_approval(loan_id)
        proof_file_id = loan["asset_proof"] if loan["asset_proof"] else None
        for admin_id in Config.ADMIN_IDS:
            try:
                if proof_file_id:
                    try:
                        await self.bot.send_photo(
                            admin_id,
                            proof_file_id,
                            caption=admin_text,
                            reply_markup=kb,
                        )
                    except Exception:
                        await self.bot.send_video(
                            admin_id,
                            proof_file_id,
                            caption=admin_text,
                            reply_markup=kb,
                        )
                else:
                    await self.bot.send_message(
                        admin_id,
                        admin_text,
                        reply_markup=kb,
                    )
            except Exception as e:
                logger.warning("Notify admin %s about loan %s: %s", admin_id, loan_id, e)
        logger.info("New loan application %s from user %s", loan_id, user_id)

    async def collateral_sent_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Пользователь нажал «Залог отправлен». Перевести займ в ожидает_залог."""
        await callback.answer()
        if not callback.from_user:
            return
        try:
            if ":" in callback.data:
                parts = callback.data.split(":", 2)
                if len(parts) >= 3:
                    loan_id = int(parts[2])
                else:
                    loan_id = None
            else:
                loan_id = None
            if not loan_id:
                user_id = callback.from_user.id
                loans = await self.db.get_user_loans(user_id, "одобрено")
                loan = loans[0] if loans else None
            else:
                loan = await self.db.get_loan(loan_id)
            if not loan or loan["status"] != "одобрено":
                await callback.message.edit_text("❌ Заявка не найдена или уже обработана.")
                return
            if loan["user_id"] != callback.from_user.id:
                await callback.message.edit_text("❌ Это не ваш займ.")
                return
            await self.db.set_loan_awaiting_collateral(loan["id"])
            await callback.message.edit_text(
                f"✅ Залог по займу #{loan['id']} отмечен как отправленный.\n\nОжидайте проверки администратором."
            )
            # Уведомить админов
            user = await self.db.get_user(loan["user_id"])
            username = (user["username"] or "").strip() if user else f"id{loan['user_id']}"
            if not username:
                username = f"id{loan['user_id']}"
            adesc = loan["asset_description"] or ""
            desc = adesc[:200]
            if len(adesc) > 200:
                desc = desc + "..."
            admin_text = (
                f"📦 <b>Залог отправлен — займ #{loan['id']}</b>\n\n"
                f"👤 Пользователь: @{username}\n"
                f"📦 Тип актива: {loan['asset_type']}\n"
                f"💰 Запрошено: {loan['requested_amount']} USDT\n"
                f"📝 Описание:\n{desc}\n\n"
                f"👉 Проверьте получение залога и нажмите кнопку ниже"
            )
            kb = InlineKeyboards.admin_loan_card_await_collateral(loan["id"])
            for admin_id in Config.ADMIN_IDS:
                try:
                    await self.bot.send_message(
                        admin_id,
                        admin_text,
                        reply_markup=kb,
                    )
                except Exception as e:
                    logger.warning("Notify admin %s about collateral sent for loan %s: %s", admin_id, loan["id"], e)
        except Exception as e:
            logger.exception("collateral_sent_callback error: %s", e)
            await callback.message.edit_text("❌ Произошла ошибка. Попробуйте позже.")

    async def info_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Обработчик кнопки «Информация»."""
        await callback.answer()
        if callback.data == "info:main":
            info_text = (
                "ℹ️ <b>Информация о сервисе</b>\n\n"
                "📋 <b>Как это работает:</b>\n"
                "1. Подайте заявку на займ под залог цифрового актива\n"
                "2. Администратор оценит актив и одобрит заявку\n"
                "3. Отправьте залог администратору\n"
                "4. После проверки залога вам будет переведена криптовалюта\n"
                "5. Погасите займ в срок через бота\n"
                "6. После полного погашения залог будет возвращён\n\n"
                "💰 <b>Условия:</b>\n"
                "• Процент: 1.5% в день\n"
                "• Минимальная сумма погашения: 0.1 USDT\n"
                "• Сроки займа: 7, 14 или 30 дней\n"
                "• Льготный период: 12 часов после срока\n\n"
                "⚠️ <b>Важно:</b>\n"
                "• Услуга без KYC\n"
                "• Вы несёте ответственность за легальность актива\n"
                "• Залог удерживается до полного погашения\n\n"
                "❓ <b>FAQ:</b>\n"
                "• Какие активы принимаются: игровые предметы (CS2/Dota 2), аккаунты соцсетей/игр, домены, NFT\n"
                "• Оплата: криптовалюта (USDT, TON, BTC)\n"
                "• Погашение: через бота, частично или полностью\n"
                "• Возврат залога: автоматически после погашения"
            )
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="loan:menu"))
            await callback.message.edit_text(info_text, reply_markup=builder.as_markup())

    async def repay_loan_callback(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Выбор займа для погашения -> показать информацию о займе -> запрос суммы."""
        await callback.answer()
        try:
            loan_id = int(callback.data.replace("repay_loan:", ""))
        except (ValueError, IndexError):
            await callback.message.edit_text("❌ Ошибка. Попробуйте снова.")
            return
        loan = await self.db.get_loan(loan_id)
        if not loan or loan["status"] != "активен":
            await callback.message.edit_text("❌ Займ не найден или не активен.")
            return
        if callback.from_user and loan["user_id"] != callback.from_user.id:
            await callback.message.edit_text("❌ Это не ваш займ.")
            return
        # Получить все погашения по займу
        repayments = await self.db.get_repayments_by_loan(loan_id)
        total_paid = sum(float(r["amount"]) for r in repayments if r["paid_at"])
        principal = float(loan["approved_amount"] or loan["requested_amount"] or 0)
        current_debt = float(loan["current_debt"] or 0)
        # Изначальный долг = current_debt + total_paid (если current_debt уже уменьшен) или пересчитываем
        # Если current_debt = 0, значит долг погашен полностью
        # Изначальный долг хранится при выдаче займа, но мы можем вычислить: если есть погашения, то изначальный = current_debt + total_paid
        if total_paid > 0:
            initial_debt = current_debt + total_paid
        else:
            # Если погашений нет, current_debt = изначальный долг
            initial_debt = current_debt if current_debt > 0 else (principal + principal * (loan["interest_rate"] or Config.INTEREST_RATE) * (loan["hold_days"] or 14))
        due_date = loan["due_date"]
        if isinstance(due_date, str):
            try:
                due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            except Exception:
                due_date = None
        due_date_str = due_date.strftime("%d.%m.%Y") if due_date else "—"
        loan_issued_at = loan["loan_issued_at"] if "loan_issued_at" in loan.keys() else None
        issued_date_str = "—"
        if loan_issued_at:
            if isinstance(loan_issued_at, str):
                try:
                    issued_date = datetime.fromisoformat(loan_issued_at.replace("Z", "+00:00"))
                    issued_date_str = issued_date.strftime("%d.%m.%Y")
                except Exception:
                    pass
        interest_rate = (loan["interest_rate"] if loan["interest_rate"] is not None else Config.INTEREST_RATE) * 100
        term_days = loan["hold_days"] or 14
        adesc = loan["asset_description"] or ""
        loan_info = (
            f"📄 <b>Займ #{loan_id}</b>\n\n"
            f"📦 <b>Залог:</b>\n"
            f"• Тип: {loan['asset_type']}\n"
            f"• Описание: {adesc[:150]}{'...' if len(adesc) > 150 else ''}\n\n"
            f"💰 <b>Финансы:</b>\n"
            f"• Выдано: <b>{principal:.2f} USDT</b>\n"
            f"• Процент: {interest_rate:.1f}% в день\n"
            f"• Срок: {term_days} дн.\n"
            f"• Всего к погашению: <b>{initial_debt:.2f} USDT</b>\n"
            f"• Уже погашено: <b>{total_paid:.2f} USDT</b>\n"
            f"• Остаток долга: <b>{current_debt:.2f} USDT</b>\n\n"
            f"📅 Дата выдачи: {issued_date_str}\n"
            f"📅 Срок погашения: {due_date_str}\n"
            f"🔄 Статус: {loan['status']}\n\n"
            f"💵 Введите сумму погашения в USDT (минимум 0.1, максимум {current_debt:.2f}):"
        )
        await state.update_data(repay_loan_id=loan_id, repay_max_amount=current_debt)
        await state.set_state(RepayStates.amount)
        await callback.message.edit_text(loan_info)

    async def repay_amount_input(self, message: Message, state: FSMContext) -> None:
        """Сумма погашения -> создание инвойса и отправка ссылки."""
        data = await state.get_data()
        loan_id = data.get("repay_loan_id")
        max_amount = data.get("repay_max_amount", 1_000_000)
        if not loan_id:
            await state.clear()
            await message.answer("⏰ Сессия истекла. Выберите «Погасить займ» снова.")
            return
        ok, amount, err = validate_amount(message.text or "", min_val=0.1, max_val=max_amount)
        if not ok:
            await message.answer(f"❌ {err}")
            return
        loan = await self.db.get_loan(loan_id)
        if not loan or loan["status"] != "активен":
            await state.clear()
            await message.answer("❌ Займ не найден или не активен.")
            return
        current_debt = float(loan["current_debt"] or 0)
        if amount > current_debt:
            amount = current_debt
        if not self.crypto:
            await message.answer("⚠️ Оплата временно недоступна.")
            await state.clear()
            return
        result = await self.crypto.create_invoice(amount=amount, asset="USDT", description=f"Погашение займа #{loan_id}")
        if not result:
            await message.answer("❌ Не удалось создать счёт. Попробуйте позже.")
            await state.clear()
            return
        invoice_id, pay_url = result
        await self.db.add_repayment(loan_id=loan_id, amount=amount, invoice_id=invoice_id, invoice_url=pay_url)
        await state.clear()
        await message.answer(
            f"💳 <b>Оплатите счёт</b> (сумма {amount} USDT):\n\n{pay_url}\n\n✅ После оплаты бот автоматически зачислит погашение."
        )
        await message.answer("🏠 Главное меню:", reply_markup=InlineKeyboards.main_menu())
