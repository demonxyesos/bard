"""Модель траффера."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Trafer:
    """Траффер (реферер) с панелью и тарифом."""

    id: int
    user_id: Optional[int] = None
    panel_token: str = ""
    fixed_rate: float = 0
    percent_rate: float = 0
    is_active: bool = True
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "Trafer":
        """Создать из строки БД."""
        return cls(
            id=row["id"],
            user_id=row["user_id"] if "user_id" in row.keys() else None,
            panel_token=row["panel_token"] or "",
            fixed_rate=float(row["fixed_rate"] or 0) if "fixed_rate" in row.keys() else 0,
            percent_rate=float(row["percent_rate"] or 0) if "percent_rate" in row.keys() else 0,
            is_active=bool(row["is_active"]) if "is_active" in row.keys() else True,
            created_at=row["created_at"] if "created_at" in row.keys() else None,
        )
