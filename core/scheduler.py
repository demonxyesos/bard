"""Фоновые задачи: проверка инвойсов, рассылки, таймер удержания, просрочка, бэкап."""
import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from .config import Config

logger = logging.getLogger(__name__)


class Scheduler:
    """Планировщик фоновых задач."""

    def __init__(self, bot_app: "BotApp"):  # noqa: F821
        self.bot_app = bot_app
        self.scheduler = AsyncIOScheduler()
        self._running = False

    def _get_bot(self):
        """Доступ к боту из контекста приложения."""
        return getattr(self.bot_app, "bot", None)

    def _get_db(self):
        return getattr(self.bot_app, "db", None)

    def _get_crypto(self):
        return getattr(self.bot_app, "crypto_service", None)

    def start(self) -> None:
        """Запуск всех задач."""
        if self._running:
            return
        # Проверка инвойсов каждые 30 секунд
        self.scheduler.add_job(
            self._check_invoices_job,
            IntervalTrigger(seconds=Config.INVOICE_POLL_INTERVAL_SEC),
            id="check_invoices",
            replace_existing=True,
        )
        # Рассылки — каждую минуту
        self.scheduler.add_job(
            self._broadcast_job,
            IntervalTrigger(minutes=1),
            id="broadcast",
            replace_existing=True,
        )
        # Проверка окончания удержания и просрочки — каждую минуту
        self.scheduler.add_job(
            self._hold_and_overdue_job,
            IntervalTrigger(minutes=1),
            id="hold_overdue",
            replace_existing=True,
        )
        # Бэкап БД раз в 6 часов
        self.scheduler.add_job(
            self._backup_job,
            IntervalTrigger(hours=Config.BACKUP_INTERVAL_HOURS),
            id="backup",
            replace_existing=True,
        )
        self.scheduler.start()
        self._running = True
        logger.info("Scheduler started")

    def stop(self) -> None:
        """Остановка планировщика."""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Scheduler stopped")

    async def _check_invoices_job(self) -> None:
        """Проверка статуса неподтверждённых инвойсов каждые 30 сек."""
        bot = self._get_bot()
        db = self._get_db()
        crypto = self._get_crypto()
        if not all((bot, db, crypto)):
            return
        try:
            pending = await db.get_pending_repayments()
            for row in pending:
                invoice_id = row["invoice_id"]
                if not invoice_id:
                    continue
                try:
                    # Проверить что repayment еще не оплачен (защита от повторной обработки)
                    repayment_check = await db.get_repayment(row["id"])
                    if not repayment_check or repayment_check["paid_at"]:
                        continue  # Уже обработано
                    status = await crypto.get_invoice_status(invoice_id)
                    if status and str(status).lower() in ("paid", "completed"):
                        # Сначала отмечаем как оплаченное, потом уменьшаем долг
                        await db.set_repayment_paid(row["id"])
                        loan = await db.get_loan(row["loan_id"])
                        if loan:
                            old_debt = float(loan["current_debt"] or 0)
                            new_debt = round(old_debt - row["amount"], 2)
                            await db.decrease_loan_debt(loan["id"], row["amount"])
                            if new_debt <= 0:
                                await db.set_loan_repaid(loan["id"])
                            if hasattr(self.bot_app, "on_repayment_paid"):
                                await self.bot_app.on_repayment_paid(row, loan, new_debt)
                except Exception as e:
                    logger.exception("check_invoices_job repayment %s: %s", row["id"], e)
        except Exception as e:
            logger.exception("check_invoices_job: %s", e)

    async def _broadcast_job(self) -> None:
        """Отправка отложенных рассылок."""
        bot = self._get_bot()
        db = self._get_db()
        if not bot or not db:
            return
        try:
            pending = await db.get_pending_broadcasts()
            for bc in pending:
                try:
                    users = await db.get_all_users()
                    # Фильтр: all / active / overdue
                    if bc["filter_type"] == "active":
                        user_ids_with_active = set()
                        for u in users:
                            loans = await db.get_user_active_loans(u["id"])
                            if loans:
                                user_ids_with_active.add(u["id"])
                        users = [u for u in users if u["id"] in user_ids_with_active]
                    elif bc["filter_type"] == "overdue":
                        user_ids_overdue = set()
                        for u in users:
                            loans = await db.get_user_loans(u["id"], "просрочен")
                            if loans:
                                user_ids_overdue.add(u["id"])
                        users = [u for u in users if u["id"] in user_ids_overdue]
                    else:
                        users = [u for u in users if not u["is_blocked"]]
                    for u in users:
                        if u["is_blocked"]:
                            continue
                        try:
                            if bc["content_type"] == "text":
                                await bot.send_message(
                                    u["id"],
                                    bc["content"] or "",
                                    parse_mode=bc["parse_mode"] or None,
                                )
                            elif bc["content_type"] == "photo":
                                await bot.send_photo(
                                    u["id"],
                                    bc["content"],
                                    caption=bc["caption"] or None,
                                    parse_mode=bc["parse_mode"] or None,
                                )
                            elif bc["content_type"] == "video":
                                await bot.send_video(
                                    u["id"],
                                    bc["content"],
                                    caption=bc["caption"] or None,
                                    parse_mode=bc["parse_mode"] or None,
                                )
                            await asyncio.sleep(Config.BROADCAST_DELAY_MS / 1000)
                        except Exception as e:
                            logger.warning("broadcast to %s: %s", u["id"], e)
                    await db.mark_broadcast_sent(bc["id"])
                except Exception as e:
                    logger.exception("broadcast id %s: %s", bc["id"], e)
        except Exception as e:
            logger.exception("broadcast_job: %s", e)

    async def _hold_and_overdue_job(self) -> None:
        """Уведомление админу о завершении удержания; перевод в просрочку."""
        bot = self._get_bot()
        db = self._get_db()
        if not bot or not db:
            return
        try:
            # Активные займы: due_date + 12ч < сейчас → просрочен
            active = await db.get_active_loans()
            grace = timedelta(hours=Config.GRACE_PERIOD_HOURS)
            now = datetime.utcnow()
            for loan in active:
                due = loan["due_date"]
                if not due:
                    continue
                if isinstance(due, str):
                    due = datetime.fromisoformat(due.replace("Z", "+00:00"))
                if now >= due + grace:
                    await db.set_loan_overdue(loan["id"])
                    if hasattr(self.bot_app, "notify_admin_overdue"):
                        await self.bot_app.notify_admin_overdue(loan)
        except Exception as e:
            logger.exception("hold_and_overdue_job: %s", e)

    async def _backup_job(self) -> None:
        """Резервное копирование БД раз в 6 часов."""
        db = self._get_db()
        if not db:
            return
        try:
            path = await db.backup()
            logger.info("Database backup created: %s", path)
        except Exception as e:
            logger.exception("backup_job: %s", e)
