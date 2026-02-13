"""Генерация и проверка капчи при /start."""
import random
import logging

logger = logging.getLogger(__name__)


class CaptchaService:
    """Кнопка «Я человек» или математический вопрос с вариантами ответов."""

    def __init__(self, use_math: bool = True, math_probability: float = 0.5):
        self.use_math = use_math
        self.math_probability = math_probability

    def generate(self) -> tuple:
        """
        Возвращает (текст_вопроса, правильный_ответ, список_вариантов).
        Для кнопочной капчи: текст = "Подтвердите, что вы человек", ответ = "human", варианты = ["Я человек"].
        Для мат. капчи: "Сколько будет 7 + 3?", ответ = "10", варианты = ["8", "10", "12"].
        """
        if self.use_math and random.random() < self.math_probability:
            a, b = random.randint(1, 15), random.randint(1, 15)
            correct = a + b
            variants = [correct, correct + random.randint(-2, 2), correct + random.randint(-3, 3)]
            variants = list(dict.fromkeys(variants))  # уникальные
            while len(variants) < 3:
                variants.append(correct + random.randint(-5, 5))
            random.shuffle(variants)
            return f"Сколько будет {a} + {b}?", str(correct), [str(v) for v in variants[:3]]
        return "Подтвердите, что вы человек", "human", ["Я человек"]
