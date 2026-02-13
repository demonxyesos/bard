"""Асинхронная работа с SQLite через aiosqlite."""
import aiosqlite
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

from .config import Config


class Database:
    """Все операции с базой данных."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.DB_PATH
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Устанавливает соединение с БД и создаёт таблицы."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self) -> None:
        """Закрывает соединение."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _create_tables(self) -> None:
        """Создаёт все таблицы при первом запуске."""
        async with self._lock:
            await self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    ref_id INTEGER DEFAULT 0,
                    trafer_id INTEGER,
                    is_blocked INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS trafers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    panel_token TEXT UNIQUE,
                    fixed_rate REAL DEFAULT 0,
                    percent_rate REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS loans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    asset_type TEXT NOT NULL,
                    asset_description TEXT NOT NULL,
                    asset_proof TEXT,
                    status TEXT NOT NULL,
                    requested_amount REAL NOT NULL,
                    approved_amount REAL,
                    current_debt REAL,
                    hold_days INTEGER,
                    hold_started TIMESTAMP,
                    hold_until TIMESTAMP,
                    due_date TIMESTAMP,
                    interest_rate REAL,
                    invoice_link TEXT,
                    loan_issued_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS repayments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    loan_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    invoice_id INTEGER,
                    invoice_url TEXT,
                    paid_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (loan_id) REFERENCES loans(id)
                );

                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_type TEXT NOT NULL,
                    content TEXT,
                    caption TEXT,
                    parse_mode TEXT,
                    send_time TIMESTAMP NOT NULL,
                    is_sent INTEGER DEFAULT 0,
                    sent_at TIMESTAMP,
                    filter_type TEXT DEFAULT 'all',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS ref_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    code TEXT UNIQUE NOT NULL,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_loans_user_id ON loans(user_id);
                CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(status);
                CREATE INDEX IF NOT EXISTS idx_loans_hold_until ON loans(hold_until);
                CREATE INDEX IF NOT EXISTS idx_loans_due_date ON loans(due_date);
                CREATE INDEX IF NOT EXISTS idx_repayments_loan_id ON repayments(loan_id);
                CREATE INDEX IF NOT EXISTS idx_broadcasts_send_time ON broadcasts(send_time);
            """)
            await self._connection.commit()

    async def execute(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
        fetch: bool = False,
        fetch_one: bool = False,
    ) -> Any:
        """Выполняет запрос с блокировкой."""
        async with self._lock:
            if params is None:
                params = ()
            if fetch_one:
                cursor = await self._connection.execute(query, params)
                row = await cursor.fetchone()
                await cursor.close()
                return row
            if fetch:
                cursor = await self._connection.execute(query, params)
                rows = await cursor.fetchall()
                await cursor.close()
                return rows
            await self._connection.execute(query, params)
            await self._connection.commit()

    # --- Users ---
    async def get_user(self, user_id: int) -> Optional[aiosqlite.Row]:
        """Получить пользователя по id."""
        return await self.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,), fetch_one=True
        )

    async def create_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        ref_id: int = 0,
        trafer_id: Optional[int] = None,
    ) -> None:
        """Создать пользователя (после капчи)."""
        await self.execute(
            """INSERT OR IGNORE INTO users (id, username, ref_id, trafer_id, is_blocked)
               VALUES (?, ?, ?, ?, 0)""",
            (user_id, username or "", ref_id or 0, trafer_id),
        )
        # Обновить username если уже был
        await self.execute(
            "UPDATE users SET username = ?, ref_id = ?, trafer_id = ? WHERE id = ?",
            (username or "", ref_id or 0, trafer_id, user_id),
        )

    async def update_user_username(self, user_id: int, username: Optional[str]) -> None:
        """Обновить username пользователя."""
        await self.execute("UPDATE users SET username = ? WHERE id = ?", (username or "", user_id))

    async def set_user_blocked(self, user_id: int, blocked: bool) -> None:
        """Заблокировать/разблокировать пользователя."""
        await self.execute(
            "UPDATE users SET is_blocked = ? WHERE id = ?", (1 if blocked else 0, user_id)
        )

    async def get_all_users(self) -> List[aiosqlite.Row]:
        """Список всех пользователей."""
        return await self.execute("SELECT * FROM users ORDER BY created_at DESC", fetch=True)

    async def search_users(self, query: str) -> List[aiosqlite.Row]:
        """Поиск по id или username (подстрока)."""
        q = f"%{query}%"
        return await self.execute(
            "SELECT * FROM users WHERE CAST(id AS TEXT) LIKE ? OR username LIKE ? ORDER BY id",
            (q, q),
            fetch=True,
        )

    # --- Trafers ---
    async def get_trafer_by_user_id(self, user_id: int) -> Optional[aiosqlite.Row]:
        """Траффер по user_id."""
        return await self.execute(
            "SELECT * FROM trafers WHERE user_id = ?", (user_id,), fetch_one=True
        )

    async def get_trafer_by_token(self, panel_token: str) -> Optional[aiosqlite.Row]:
        """Траффер по panel_token."""
        return await self.execute(
            "SELECT * FROM trafers WHERE panel_token = ? AND is_active = 1",
            (panel_token,),
            fetch_one=True,
        )

    async def create_trafer(self, user_id: int, panel_token: str) -> Optional[int]:
        """Создать траффера. Возвращает id или None при дубликате."""
        try:
            await self.execute(
                "INSERT INTO trafers (user_id, panel_token, fixed_rate, percent_rate) VALUES (?, ?, 0, 0)",
                (user_id, panel_token),
            )
            row = await self.execute(
                "SELECT id FROM trafers WHERE user_id = ?", (user_id,), fetch_one=True
            )
            return row["id"] if row else None
        except Exception:
            return None

    async def update_trafer_rates(self, trafer_id: int, fixed_rate: float, percent_rate: float) -> None:
        """Обновить тариф траффера."""
        await self.execute(
            "UPDATE trafers SET fixed_rate = ?, percent_rate = ? WHERE id = ?",
            (fixed_rate, percent_rate, trafer_id),
        )

    async def get_all_trafers(self) -> List[aiosqlite.Row]:
        """Список всех трафферов."""
        return await self.execute("SELECT * FROM trafers ORDER BY id", fetch=True)

    # --- Loans ---
    async def create_loan(
        self,
        user_id: int,
        asset_type: str,
        asset_description: str,
        asset_proof: str,
        requested_amount: float,
        hold_days: int,
        interest_rate: float,
    ) -> int:
        """Создать заявку. Возвращает id займа."""
        await self.execute(
            """INSERT INTO loans (user_id, asset_type, asset_description, asset_proof, status,
               requested_amount, hold_days, interest_rate)
               VALUES (?, ?, ?, ?, 'ожидает_одобрения', ?, ?, ?)""",
            (user_id, asset_type, asset_description, asset_proof, requested_amount, hold_days, interest_rate),
        )
        row = await self.execute(
            "SELECT id FROM loans WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
            fetch_one=True,
        )
        return row["id"]

    async def get_loan(self, loan_id: int) -> Optional[aiosqlite.Row]:
        """Получить займ по id."""
        return await self.execute("SELECT * FROM loans WHERE id = ?", (loan_id,), fetch_one=True)

    async def update_loan_status(self, loan_id: int, status: str) -> None:
        """Обновить статус займа."""
        await self.execute(
            "UPDATE loans SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.utcnow().isoformat(), loan_id),
        )

    async def approve_loan(self, loan_id: int, approved_amount: float) -> None:
        """Одобрить заявку."""
        await self.execute(
            "UPDATE loans SET status = 'одобрено', approved_amount = ?, updated_at = ? WHERE id = ?",
            (approved_amount, datetime.utcnow().isoformat(), loan_id),
        )

    async def reject_loan(self, loan_id: int) -> None:
        """Отклонить заявку."""
        await self.update_loan_status(loan_id, "отклонён")

    async def set_loan_awaiting_collateral(self, loan_id: int) -> None:
        """Пользователь отправил залог — ожидаем проверки админом."""
        await self.update_loan_status(loan_id, "ожидает_залог")

    async def set_loan_hold_started(self, loan_id: int, hold_days: int) -> None:
        """Залог получен, запускаем таймер удержания."""
        from datetime import timedelta
        now = datetime.utcnow()
        hold_until = now + timedelta(days=hold_days)
        await self.execute(
            """UPDATE loans SET status = 'период_удержания', hold_days = ?, hold_started = ?,
               hold_until = ?, updated_at = ? WHERE id = ?""",
            (hold_days, now.isoformat(), hold_until.isoformat(), now.isoformat(), loan_id),
        )

    async def set_loan_active(
        self,
        loan_id: int,
        invoice_link: str,
        due_date: datetime,
        total_debt: float,
    ) -> None:
        """Займ выдан, статус активен."""
        now = datetime.utcnow()
        await self.execute(
            """UPDATE loans SET status = 'активен', invoice_link = ?, loan_issued_at = ?,
               due_date = ?, current_debt = ?, updated_at = ? WHERE id = ?""",
            (invoice_link, now.isoformat(), due_date.isoformat(), total_debt, now.isoformat(), loan_id),
        )

    async def decrease_loan_debt(self, loan_id: int, amount: float) -> None:
        """Уменьшить остаток долга (частичное погашение)."""
        await self.execute(
            "UPDATE loans SET current_debt = current_debt - ?, updated_at = ? WHERE id = ?",
            (amount, datetime.utcnow().isoformat(), loan_id),
        )

    async def set_loan_overdue(self, loan_id: int) -> None:
        """Поставить статус просрочен."""
        await self.update_loan_status(loan_id, "просрочен")

    async def set_loan_repaid(self, loan_id: int) -> None:
        """Долг погашен полностью."""
        await self.update_loan_status(loan_id, "погашен")

    async def set_loan_completed(self, loan_id: int) -> None:
        """Залог возвращён, сделка завершена."""
        await self.update_loan_status(loan_id, "завершён")

    async def get_loans_by_status(self, status: str) -> List[aiosqlite.Row]:
        """Список займов по статусу."""
        return await self.execute("SELECT * FROM loans WHERE status = ? ORDER BY id DESC", (status,), fetch=True)

    async def get_loans_awaiting_approval(self) -> List[aiosqlite.Row]:
        return await self.get_loans_by_status("ожидает_одобрения")

    async def get_loans_awaiting_collateral(self) -> List[aiosqlite.Row]:
        return await self.get_loans_by_status("ожидает_залог")

    async def get_loans_in_hold(self) -> List[aiosqlite.Row]:
        return await self.get_loans_by_status("период_удержания")

    async def get_active_loans(self) -> List[aiosqlite.Row]:
        return await self.get_loans_by_status("активен")

    async def get_overdue_loans(self) -> List[aiosqlite.Row]:
        return await self.get_loans_by_status("просрочен")

    async def get_loans_hold_finished(self) -> List[aiosqlite.Row]:
        """Займы, у которых hold_until <= сейчас (нужно отправить займ)."""
        return await self.execute(
            """SELECT * FROM loans WHERE status = 'период_удержания' AND hold_until <= ?""",
            (datetime.utcnow().isoformat(),),
            fetch=True,
        )

    async def get_loans_repaid_awaiting_return(self) -> List[aiosqlite.Row]:
        return await self.get_loans_by_status("погашен")

    async def get_user_loans(self, user_id: int, status: Optional[str] = None) -> List[aiosqlite.Row]:
        """Займы пользователя, опционально по статусу."""
        if status:
            return await self.execute(
                "SELECT * FROM loans WHERE user_id = ? AND status = ? ORDER BY id DESC",
                (user_id, status),
                fetch=True,
            )
        return await self.execute(
            "SELECT * FROM loans WHERE user_id = ? ORDER BY id DESC", (user_id,), fetch=True
        )

    async def get_user_active_loans(self, user_id: int) -> List[aiosqlite.Row]:
        return await self.get_user_loans(user_id, "активен")

    async def get_all_loans(self) -> List[aiosqlite.Row]:
        return await self.execute("SELECT * FROM loans ORDER BY id DESC", fetch=True)

    # --- Repayments ---
    async def add_repayment(
        self,
        loan_id: int,
        amount: float,
        invoice_id: Optional[int] = None,
        invoice_url: Optional[str] = None,
    ) -> None:
        """Добавить запись о погашении. paid_at = NULL до оплаты инвойса."""
        now = datetime.utcnow().isoformat()
        await self.execute(
            """INSERT INTO repayments (loan_id, amount, invoice_id, invoice_url, paid_at, created_at)
               VALUES (?, ?, ?, ?, NULL, ?)""",
            (loan_id, amount, invoice_id, invoice_url, now),
        )

    async def get_repayments_by_loan(self, loan_id: int) -> List[aiosqlite.Row]:
        return await self.execute(
            "SELECT * FROM repayments WHERE loan_id = ? ORDER BY id", (loan_id,), fetch=True
        )

    # --- Pending invoices (для polling) ---
    async def get_pending_invoice_loans(self) -> List[aiosqlite.Row]:
        """Займы с неподтверждёнными инвойсами (храним invoice_id в repayments или в отдельном поле).
         По ТЗ проверяем инвойсы на погашение — они создаются ботом и записываются в repayments с paid_at = NULL.
         Упростим: храним в repayments invoice_id, invoice_url, paid_at. Если paid_at NULL — проверяем."""
        return await self.execute(
            """SELECT l.* FROM loans l
               JOIN repayments r ON r.loan_id = l.id
               WHERE r.paid_at IS NULL AND r.invoice_id IS NOT NULL AND l.status = 'активен'
               GROUP BY l.id""",
            fetch=True,
        )

    async def get_pending_repayments(self) -> List[aiosqlite.Row]:
        """Записи repayments с неоплаченным инвойсом (paid_at IS NULL, invoice_id не NULL)."""
        return await self.execute(
            "SELECT * FROM repayments WHERE paid_at IS NULL AND invoice_id IS NOT NULL",
            fetch=True,
        )

    async def set_repayment_paid(self, repayment_id: int) -> None:
        """Отметить погашение как оплаченное."""
        await self.execute(
            "UPDATE repayments SET paid_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), repayment_id),
        )

    async def get_repayment(self, repayment_id: int) -> Optional[aiosqlite.Row]:
        """Получить запись о погашении по id."""
        return await self.execute(
            "SELECT * FROM repayments WHERE id = ?", (repayment_id,), fetch_one=True
        )

    # --- Broadcasts ---
    async def create_broadcast(
        self,
        content_type: str,
        send_time: datetime,
        content: Optional[str] = None,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        filter_type: str = "all",
    ) -> int:
        """Создать рассылку. content для text — текст, для photo/video — file_id после загрузки."""
        await self.execute(
            """INSERT INTO broadcasts (content_type, content, caption, parse_mode, send_time, filter_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (content_type, content or "", caption or "", parse_mode or "", send_time.isoformat(), filter_type),
        )
        row = await self.execute(
            "SELECT id FROM broadcasts ORDER BY id DESC LIMIT 1", fetch_one=True
        )
        return row["id"] if row else 0

    async def get_pending_broadcasts(self) -> List[aiosqlite.Row]:
        """Рассылки, которые нужно отправить (send_time <= сейчас, is_sent = 0)."""
        return await self.execute(
            "SELECT * FROM broadcasts WHERE is_sent = 0 AND send_time <= ?",
            (datetime.utcnow().isoformat(),),
            fetch=True,
        )

    async def mark_broadcast_sent(self, broadcast_id: int) -> None:
        """Отметить рассылку как отправленную."""
        await self.execute(
            "UPDATE broadcasts SET is_sent = 1, sent_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), broadcast_id),
        )

    # --- Ref links ---
    async def get_ref_link_by_code(self, code: str) -> Optional[aiosqlite.Row]:
        """Получить рефссылку по коду (start payload)."""
        return await self.execute(
            "SELECT * FROM ref_links WHERE code = ?", (code,), fetch_one=True
        )

    async def create_ref_link(self, name: str, code: str, created_by: int) -> None:
        await self.execute(
            "INSERT INTO ref_links (name, code, created_by) VALUES (?, ?, ?)",
            (name, code, created_by),
        )

    # --- Statistics ---
    async def get_stats(self, days: Optional[int] = None) -> dict:
        """Статистика: кол-во заявок, выданных займов, сумма и т.д."""
        since = ""
        params: Tuple[Any, ...] = ()
        if days is not None:
            since = "AND created_at >= datetime('now', ?)"
            params = (f"-{days} days",)
        total_loans = await self.execute(
            f"SELECT COUNT(*) as c FROM loans WHERE 1=1 {since}".replace("  ", " "),
            params if params else None,
            fetch_one=True,
        )
        total_issued = await self.execute(
            f"""SELECT COUNT(*) as c, COALESCE(SUM(approved_amount), 0) as s FROM loans
                WHERE status IN ('активен', 'погашен', 'завершён', 'просрочен') AND loan_issued_at IS NOT NULL {since}""".replace("  ", " "),
            params if params else None,
            fetch_one=True,
        )
        return {
            "total_loans": total_loans["c"] if total_loans else 0,
            "issued_count": total_issued["c"] if total_issued else 0,
            "issued_sum": total_issued["s"] if total_issued else 0,
        }

    # --- Backup ---
    async def backup(self) -> str:
        """Создаёт копию БД. Возвращает путь к файлу копии."""
        import shutil
        Path("backups").mkdir(exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
        backup_path = f"backups/bot_{stamp}.db"
        shutil.copy2(self.db_path, backup_path)
        return backup_path
