"""Модель займа."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Loan:
    """Заявка на займ под залог цифрового актива."""

    id: int
    user_id: int
    asset_type: str
    asset_description: str
    asset_proof: Optional[str] = None
    status: str = "ожидает_одобрения"
    requested_amount: float = 0
    approved_amount: Optional[float] = None
    current_debt: Optional[float] = None
    hold_days: Optional[int] = None
    hold_started: Optional[datetime] = None
    hold_until: Optional[datetime] = None
    due_date: Optional[datetime] = None
    interest_rate: float = 0.015
    invoice_link: Optional[str] = None
    loan_issued_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "Loan":
        """Создать из строки БД."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            asset_type=row["asset_type"],
            asset_description=row["asset_description"],
            asset_proof=row["asset_proof"] if "asset_proof" in row.keys() else None,
            status=row["status"],
            requested_amount=row["requested_amount"] or 0,
            approved_amount=row["approved_amount"] if "approved_amount" in row.keys() else None,
            current_debt=row["current_debt"] if "current_debt" in row.keys() else None,
            hold_days=row["hold_days"] if "hold_days" in row.keys() else None,
            hold_started=row["hold_started"] if "hold_started" in row.keys() else None,
            hold_until=row["hold_until"] if "hold_until" in row.keys() else None,
            due_date=row["due_date"] if "due_date" in row.keys() else None,
            interest_rate=row["interest_rate"] if "interest_rate" in row.keys() else 0.015,
            invoice_link=row["invoice_link"] if "invoice_link" in row.keys() else None,
            loan_issued_at=row["loan_issued_at"] if "loan_issued_at" in row.keys() else None,
            created_at=row["created_at"] if "created_at" in row.keys() else None,
            updated_at=row["updated_at"] if "updated_at" in row.keys() else None,
        )


LOAN_STATUSES = [
    "ожидает_одобрения",
    "одобрено",
    "ожидает_залог",
    "период_удержания",
    "активен",
    "просрочен",
    "погашен",
    "завершён",
    "отклонён",
]

ASSET_TYPES = ["игровой предмет", "аккаунт", "домен", "NFT"]
