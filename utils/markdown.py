"""Экранирование текста для MarkdownV2 Telegram."""
import re

# Символы, которые нужно экранировать в MarkdownV2
MD2_ESCAPE = r"_*[]()~`>#+-=|{}.!"


def escape_markdown_v2(text: str) -> str:
    """
    Экранирует специальные символы для MarkdownV2.
    Символы: _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+=|{}.!\-])", r"\\\1", text)
