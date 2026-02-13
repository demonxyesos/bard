"""Точка входа: класс BotApp, инициализация бота и регистрация обработчиков."""
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import Config
from .database import Database
from .scheduler import Scheduler
from services.crypto_service import CryptoService
from services.finance_service import FinanceService
from services.captcha_service import CaptchaService
from handlers.user_handler import UserHandler
from handlers.admin_handler import AdminHandler
from handlers.trafer_handler import TraferHandler
from keyboards.inline_keyboards import InlineKeyboards

# Логирование в файл
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class BotApp:
    """Точка входа: бот, БД, планировщик, сервисы, обработчики."""

    def __init__(self):
        self.bot = Bot(
            token=Config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher()
        self.db = Database()
        self.crypto_service = CryptoService(Config.CRYPTO_API_KEY)
        self.finance_service = FinanceService(Config.INTEREST_RATE, Config.PENALTY_RATE)
        self.captcha_service = CaptchaService(use_math=True, math_probability=0.5)
        self.scheduler = Scheduler(self)

        user_handler = UserHandler(
            bot=self.bot,
            db=self.db,
            config=Config,
            captcha_service=self.captcha_service,
            finance_service=self.finance_service,
            crypto_service=self.crypto_service,
        )
        admin_handler = AdminHandler(
            bot=self.bot,
            db=self.db,
            config=Config,
            finance_service=self.finance_service,
        )
        trafer_handler = TraferHandler(bot=self.bot, db=self.db, config=Config)

        user_handler.register()
        admin_handler.register()
        trafer_handler.register()

        # Порядок: траффер (panel_), пользователь (start), админ
        self.dp.include_router(trafer_handler.router)
        self.dp.include_router(user_handler.router)
        self.dp.include_router(admin_handler.router)

    async def on_repayment_paid(self, repayment_row, loan_row, new_debt: float) -> None:
        """Вызывается планировщиком при подтверждении оплаты инвойса погашения."""
        try:
            await self.bot.send_message(
                loan_row["user_id"],
                f"✅ <b>Погашение займа #{loan_row['id']} зачислено.</b>\n\nОстаток долга: <b>{new_debt:.2f} USDT</b>.",
            )
            for admin_id in Config.ADMIN_IDS:
                await self.bot.send_message(
                    admin_id,
                    f"💰 Погашение по займу #{loan_row['id']}: <b>{repayment_row['amount']} USDT</b>. Остаток: <b>{new_debt:.2f} USDT</b>.",
                )
        except Exception as e:
            logger.exception("on_repayment_paid: %s", e)

    async def notify_admin_overdue(self, loan_row) -> None:
        """Уведомить админа о просрочке займа."""
        text = f"⚠️ <b>Займ #{loan_row['id']} просрочен</b> (пользователь id {loan_row['user_id']})."
        for admin_id in Config.ADMIN_IDS:
            try:
                await self.bot.send_message(admin_id, text)
            except Exception as e:
                logger.warning("notify_admin_overdue %s: %s", admin_id, e)

    async def start(self) -> None:
        """Запуск бота: подключение БД, планировщик, polling."""
        await self.db.connect()
        self.scheduler.start()
        logger.info("Bot starting (polling)")
        try:
            await self.dp.start_polling(self.bot)
        finally:
            self.scheduler.stop()
            await self.db.close()
            await self.crypto_service.close()
