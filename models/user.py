"""Модель пользователя."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Пользователь бота. Идентификатор — Telegram user_id."""

    id: int
    username: Optional[str] = None
    ref_id: int = 0
    trafer_id: Optional[int] = None
    is_blocked: bool = False
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "User":
        """Создать из строки БД (aiosqlite.Row)."""
        return cls(
            id=row["id"],
            username=row["username"] or None,
            ref_id=row["ref_id"] or 0,
            trafer_id=row["trafer_id"],
            is_blocked=bool(row["is_blocked"]),
            created_at=row["created_at"],
        )
