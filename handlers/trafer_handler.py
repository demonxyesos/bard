"""Панель траффера: доступ по ссылке panel_{token}."""
import logging
from datetime import datetime
from aiogram import Bot, F, Router
from aiogram.filters import CommandStart, BaseFilter
from aiogram.types import CallbackQuery, Message

from core.config import Config
from keyboards.inline_keyboards import InlineKeyboards
from handlers.base_handler import BaseHandler

logger = logging.getLogger(__name__)


class PanelDeepLinkFilter(BaseFilter):
    """Фильтр: только /start с аргументом panel_xxx."""
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        parts = message.text.strip().split(maxsplit=1)
        return len(parts) >= 2 and parts[1].strip().startswith("panel_")


class TraferHandler(BaseHandler):
    """Обработчики панели траффера."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.router = Router(name="trafer")

    def register(self) -> None:
        self.router.message.register(
            self.cmd_start_panel,
            CommandStart(),
            PanelDeepLinkFilter(),
        )
        self.router.callback_query.register(self.trafer_ref_link, F.data == "trafer:ref_link")
        self.router.callback_query.register(self.trafer_history, F.data == "trafer:history")

    async def cmd_start_panel(self, message: Message) -> None:
        """Обработка /start panel_xxx — показать панель траффера."""
        if not message.text or not message.from_user:
            return
        parts = message.text.strip().split(maxsplit=1)
        token = parts[1].strip().replace("panel_", "", 1).strip() if len(parts) >= 2 else ""
        if not token:
            return
        trafer = await self.db.get_trafer_by_token(token)
        if not trafer:
            await message.answer("❌ Ссылка недействительна или панель отключена.")
            return
        trafer_id = trafer["id"]
        user_id_trafer = trafer["user_id"]
        # Рефералы: пользователи с trafer_id = trafer_id (в users trafer_id хранит id траффера из trafers)
        all_users = await self.db.get_all_users()
        refs = [u for u in all_users if u["trafer_id"] == trafer_id]
        ref_ids = [u["id"] for u in refs]
        # Активные займы рефералов
        all_loans = await self.db.get_all_loans()
        active_loans = [l for l in all_loans if l["user_id"] in ref_ids and l["status"] == "активен"]
        # Оборот за месяц (сумма выданных займов рефералов за текущий месяц)
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        loans_issued = [l for l in all_loans if l["user_id"] in ref_ids and l.get("loan_issued_at") and l["status"] in ("активен", "погашен", "завершён", "просрочен")]
        turnover = 0
        for l in loans_issued:
            issued = l.get("loan_issued_at")
            if isinstance(issued, str):
                try:
                    issued = datetime.fromisoformat(issued.replace("Z", "+00:00"))
                except Exception:
                    continue
            if issued and issued >= month_start:
                turnover += float(l.get("approved_amount") or l.get("requested_amount") or 0)
        fixed = float(trafer["fixed_rate"] or 0)
        percent = float(trafer["percent_rate"] or 0)
        earnings = fixed * len(refs) + (percent / 100) * turnover
        # Топ-5 рефералов по сумме займов (упрощённо — по количеству займов)
        ref_loan_count = {}
        for l in all_loans:
            if l["user_id"] in ref_ids:
                ref_loan_count[l["user_id"]] = ref_loan_count.get(l["user_id"], 0) + 1
        top_refs = sorted(refs, key=lambda u: ref_loan_count.get(u["id"], 0), reverse=True)[:5]
        top_text = "\n".join([f"  @{u['username'] or u['id']} — займов: {ref_loan_count.get(u['id'], 0)}" for u in top_refs]) or "  —"
        text = (
            f"📊 <b>Панель траффера</b>\n\n"
            f"👥 Привлечённых рефералов: <b>{len(refs)}</b>\n"
            f"💳 Активных займов рефералов: <b>{len(active_loans)}</b>\n"
            f"💰 Оборот за месяц: <b>{turnover:.2f} USDT</b>\n"
            f"📈 Тариф: фикс {fixed} USDT + {percent}%\n"
            f"💵 Заработок: <b>{earnings:.2f} USDT</b>\n\n"
            f"🏆 Топ-5 рефералов:\n{top_text}"
        )
        await message.answer(text, reply_markup=InlineKeyboards.trafer_panel())

    async def trafer_ref_link(self, callback: CallbackQuery) -> None:
        """Кнопка «Моя рефссылка» — показать ссылку для привлечения."""
        if not callback.from_user:
            await callback.answer()
            return
        trafer = await self.db.get_trafer_by_user_id(callback.from_user.id)
        if not trafer:
            await callback.answer("У вас нет панели траффера.")
            return
        bot_info = await self.bot.get_me()
        username = bot_info.username if bot_info else "bot"
        ref_id = trafer["user_id"]
        link = f"https://t.me/{username}?start=ref_{ref_id}"
        await callback.message.answer(f"🔗 <b>Ваша реферальная ссылка:</b>\n\n{link}")
        await callback.answer()

    async def trafer_history(self, callback: CallbackQuery) -> None:
        """Кнопка «История» — список начислений (пока заглушка)."""
        await callback.answer("📜 История начислений будет отображаться здесь после реализации учёта выплат.")