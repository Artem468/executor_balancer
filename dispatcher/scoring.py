from typing import Dict, Any, List, Union, Tuple, Optional
import datetime
from dataclasses import dataclass


@dataclass
class ParamScore:
    value: float
    weight: float
    matches: bool

    @property
    def weighted_score(self) -> float:
        return self.value * self.weight if self.matches else 0.0


class ParameterMatcher:
    """Класс для сопоставления параметров с учетом типов данных и операторов"""
    
    OPERATOR_MAP = {
        "EQ": lambda x, y: x == y,
        "NE": lambda x, y: x != y,
        "GT": lambda x, y: x > y,
        "LT": lambda x, y: x < y,
        "GTE": lambda x, y: x >= y,
        "LTE": lambda x, y: x <= y,
    }

    @classmethod
    def normalize_value(cls, value: Any) -> Any:
        """Нормализация значений для сравнения"""
        if isinstance(value, str) and "T" in value:
            try:
                return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return value

    @classmethod
    def compare_values(cls, user_value: Any, request_condition: Dict[str, Any]) -> Tuple[bool, float]:
        """
        Сравнивает значение параметра пользователя с условием из заявки
        Возвращает tuple(соответствует ли условию, вес параметра)
        """
        if user_value is None:
            return False, 0.0

        value = cls.normalize_value(request_condition.get("value"))
        operator = request_condition.get("operator", "EQ")
        height = float(request_condition.get("height", 1.0))

        if operator not in cls.OPERATOR_MAP:
            return False, height

        try:
            matches = cls.OPERATOR_MAP[operator](user_value, value)
            return matches, height
        except (TypeError, ValueError):
            return False, height


class UserScorer:
    """Класс для расчета соответствия пользователя заявке"""

    def __init__(self, min_score_fraction: float = 0.7):
        self.min_score_threshold = min_score_fraction

    def calculate_parameter_scores(
        self, user_params: Dict[str, Any], request_params: Dict[str, Dict[str, Any]]
    ) -> List[ParamScore]:
        """Вычисляет оценки для каждого параметра"""
        scores = []
        
        for key, condition in request_params.items():
            user_value = user_params.get(key)
            matches, weight = ParameterMatcher.compare_values(user_value, condition)

            base_score = 1.0 if matches else 0.0

            if matches and isinstance(user_value, (int, float)) and isinstance(condition["value"], (int, float)):
                try:
                    diff = abs(user_value - condition["value"])
                    max_val = max(abs(user_value), abs(condition["value"]))
                    if max_val != 0:
                        precision_factor = 1 - (diff / max_val)
                        base_score = max(base_score * precision_factor, 0.0)
                except (TypeError, ZeroDivisionError):
                    pass

            scores.append(ParamScore(base_score, weight, matches))

        return scores

    def calculate_total_score(
        self, parameter_scores: List[ParamScore]
    ) -> Tuple[float, float]:
        """Вычисляет общую оценку и максимально возможную оценку"""
        total_score = 0.0
        max_possible_score = 0.0

        for score in parameter_scores:
            total_score += score.weighted_score
            max_possible_score += score.weight

        return total_score, max_possible_score

    def is_suitable_candidate(
        self, total_score: float, max_possible_score: float
    ) -> bool:
        """Проверяет, подходит ли кандидат по минимальному порогу оценки"""
        if max_possible_score == 0:
            return True
        return (total_score / max_possible_score) >= self.min_score_threshold

    @staticmethod
    def create_fallback_candidate(
        user_id: str,
        daily_requests: int,
        max_daily_requests: Optional[int]
    ) -> 'CandidateInfo':
        """
        Создает запасного кандидата для случая, когда нет подходящих по параметрам.
        Использует только информацию о нагрузке.
        """
        return CandidateInfo(
            user_id=user_id,
            total_score=0.0,
            max_score=0.0,
            daily_requests=daily_requests,
            max_daily_requests=max_daily_requests,
        )


class LoadBalancer:
    """Класс для балансировки нагрузки между пользователями"""

    @staticmethod
    def calculate_load_factor(
        daily_requests: int,
        max_daily_requests: Union[int, None],
        total_score: float,
        max_possible_score: float,
        ignore_score: bool = False
    ) -> float:
        """
        Вычисляет фактор нагрузки пользователя
        Возвращает значение от 0 до 1, где меньшее значение означает лучшего кандидата
        
        Args:
            daily_requests: Количество заявок за день
            max_daily_requests: Максимальное количество заявок в день (может быть None)
            total_score: Общий счет соответствия параметрам
            max_possible_score: Максимально возможный счет
            ignore_score: Если True, игнорирует score и учитывает только нагрузку
        """
        if max_daily_requests is None or max_daily_requests == 0:
            load_factor = daily_requests / (daily_requests + 1)
        else:
            load_factor = daily_requests / max_daily_requests

        if ignore_score:
            return load_factor

        score_factor = (
            total_score / max_possible_score if max_possible_score > 0 else 1.0
        )

        return (0.7 * load_factor) + (0.3 * (1 - score_factor))

    @staticmethod
    def get_fallback_load_factor(
        daily_requests: int,
        max_daily_requests: Union[int, None]
    ) -> float:
        """
        Вычисляет фактор нагрузки для случая, когда нет подходящих по параметрам кандидатов.
        Учитывает только количество заявок, игнорируя соответствие параметрам.
        """
        if max_daily_requests is None or max_daily_requests == 0:
            return daily_requests / (daily_requests + 1)
        else:
            return daily_requests / max_daily_requests