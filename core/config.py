from typing import List


class Config:
    BOT_TOKEN: str = "токен бота"
    CRYPTO_API_KEY: str = "@send тут в крипто пэй надо приложение сделать"
    ADMIN_IDS: List[int] = [7671147870]
    INTEREST_RATE: float = 0.015
    PENALTY_RATE: float = 0.02
    DEFAULT_REF_ID: int = 7671147870
    DB_PATH: str = "bot.db"
    BACKUP_INTERVAL_HOURS: int = 6
    INVOICE_POLL_INTERVAL_SEC: int = 30
    BROADCAST_DELAY_MS: int = 50
    GRACE_PERIOD_HOURS: int = 12

    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        return user_id in cls.ADMIN_IDS
