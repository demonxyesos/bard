"""Расчёт процентов, штрафов и остатка долга."""
from datetime import datetime, timedelta
from typing import Optional


class FinanceService:
    """Расчёт процентов и штрафов. Проценты не пересчитываются при частичном погашении."""

    def __init__(self, interest_rate: float = 0.015, penalty_rate: float = 0.02):
        self.interest_rate = interest_rate  # 1.5% в день
        self.penalty_rate = penalty_rate  # штраф за просрочку

    def calculate_total_debt(
        self,
        principal: float,
        days: int,
        interest_rate: Optional[float] = None,
    ) -> float:
        """
        Итоговая сумма долга: тело займа + проценты за срок.
        Пример: 420 USDT на 14 дней при 1.5%/день → 420 + 420 * 0.015 * 14 = 508.2
        """
        rate = interest_rate if interest_rate is not None else self.interest_rate
        interest = principal * rate * days
        return round(principal + interest, 2)

    def calculate_due_date(self, issue_date: datetime, days: int) -> datetime:
        """Дата погашения = дата выдачи + срок в днях."""
        return issue_date + timedelta(days=days)

    def remaining_debt_after_payment(self, current_debt: float, payment: float) -> float:
        """Остаток долга после частичного погашения. Не пересчитываем проценты."""
        return max(0, round(current_debt - payment, 2))

    def penalty_for_overdue(self, amount: float, days_overdue: int) -> float:
        """Штраф за просрочку (если понадобится в будущем)."""
        return round(amount * self.penalty_rate * days_overdue, 2)
