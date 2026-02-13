"""Работа с CryptoBot API через aiocryptopay."""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class CryptoService:
    """Создание инвойсов на погашение и проверка статуса."""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self._client = None

    async def _get_client(self):
        """Ленивая инициализация клиента aiocryptopay."""
        if self._client is None and self.api_token:
            try:
                from aiocryptopay import AioCryptoPay, Networks
                self._client = AioCryptoPay(token=self.api_token, network=Networks.MAIN_NET)
            except Exception as e:
                logger.exception("CryptoPay client init: %s", e)
        return self._client

    async def create_invoice(
        self,
        amount: float,
        asset: str = "USDT",
        description: Optional[str] = None,
    ) -> Optional[Tuple[int, str]]:
        """
        Создать инвойс на погашение.
        Возвращает (invoice_id, pay_url) или None.
        """
        client = await self._get_client()
        if not client:
            return None
        try:
            # aiocryptopay: create_invoice(asset='USDT', amount=100)
            result = await client.create_invoice(asset=asset, amount=amount)
            if result and getattr(result, "invoice_id", None):
                inv_id = result.invoice_id
                pay_url = getattr(result, "pay_url", None) or getattr(result, "bot_invoice_url", None)
                if not pay_url and hasattr(result, "link"):
                    pay_url = result.link
                # Стандартный вид ссылки: https://t.me/CryptoBot?start=invoice_xxx
                if not pay_url and inv_id:
                    pay_url = f"https://t.me/CryptoBot?start=invoice_{inv_id}"
                return (inv_id, pay_url or "")
            return None
        except Exception as e:
            logger.exception("create_invoice: %s", e)
            return None

    async def get_invoice_status(self, invoice_id: int) -> Optional[str]:
        """Проверить статус инвойса. Возвращает 'paid', 'active', 'expired' и т.д."""
        client = await self._get_client()
        if not client:
            return None
        try:
            # get_invoices(invoice_ids=[id])
            result = await client.get_invoices(invoice_ids=[invoice_id])
            if result is None:
                return None
            # Может быть список или один объект
            if isinstance(result, list) and result:
                item = result[0]
            else:
                item = result
            status = getattr(item, "status", None)
            if status is not None:
                return str(status).lower()
            return None
        except Exception as e:
            logger.debug("get_invoice_status %s: %s", invoice_id, e)
            return None

    async def close(self) -> None:
        """Закрыть клиент при необходимости."""
        if self._client and hasattr(self._client, "close"):
            try:
                await self._client.close()
            except Exception:
                pass
        self._client = None
