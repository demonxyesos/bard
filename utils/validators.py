"""Валидация ввода пользователя."""
import re
from typing import Optional, Tuple


def validate_amount(text: str, min_val: float = 0.1, max_val: float = 1_000_000) -> Tuple[bool, Optional[float], str]:
    """
    Проверка суммы в USDT.
    Возвращает (ok, value, error_message).
    """
    text = (text or "").strip().replace(",", ".")
    try:
        val = float(text)
        if val < min_val:
            return False, None, f"Минимальная сумма {min_val} USDT."
        if val > max_val:
            return False, None, f"Максимальная сумма {max_val} USDT."
        return True, round(val, 2), ""
    except ValueError:
        return False, None, "Введите число (например: 100 или 100.50)."


def validate_days(text: str, allowed: Optional[list] = None) -> Tuple[bool, Optional[int], str]:
    """
    Проверка количества дней. allowed = [7, 14, 30] или None (любое положительное).
    """
    text = (text or "").strip()
    try:
        val = int(text)
        if val < 1:
            return False, None, "Введите положительное число дней."
        if allowed is not None and val not in allowed:
            return False, None, f"Допустимые сроки: {', '.join(map(str, allowed))} дней."
        return True, val, ""
    except ValueError:
        return False, None, "Введите целое число (например: 7 или 14)."


# Ссылка на чек CryptoBot: https://t.me/CryptoBot?start=invoice_xxx или t.me/CryptoBot?start=invoice_xxx
INVOICE_LINK_PATTERN = re.compile(
    r"https?://(?:www\.)?t\.me/CryptoBot\?start=invoice_[a-zA-Z0-9_-]+",
    re.IGNORECASE,
)


def validate_invoice_link(text: str) -> Tuple[bool, Optional[str], str]:
    """Проверка ссылки на инвойс CryptoBot. Возвращает (ok, link, error_message)."""
    text = (text or "").strip()
    match = INVOICE_LINK_PATTERN.search(text)
    if match:
        return True, match.group(0), ""
    if "CryptoBot" in text and "invoice" in text:
        return False, None, "Ссылка должна быть вида: https://t.me/CryptoBot?start=invoice_xxx"
    return False, None, "Отправьте ссылку на чек из @CryptoBot (например: https://t.me/CryptoBot?start=invoice_xxx)."
