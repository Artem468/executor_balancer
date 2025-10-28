from mongoengine import Document, StringField
from django.core.exceptions import ValidationError
import datetime

from core.models import KeyDataTypes


def cast_param_value(value, type_name: str):
    """Преобразует значение по типу"""
    if type_name == "string":
        return str(value)
    elif type_name == "integer":
        try:
            return int(value)
        except Exception:
            raise ValidationError(f"Невозможно преобразовать '{value}' в integer")
    elif type_name == "float":
        try:
            return float(value)
        except Exception:
            raise ValidationError(f"Невозможно преобразовать '{value}' в float")
    elif type_name == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    elif type_name == "datetime":
        if isinstance(value, datetime.datetime):
            return value
        try:
            return datetime.datetime.fromisoformat(value)
        except Exception:
            raise ValidationError(f"Некорректный формат даты: {value}")
    return str(value)  # fallback


def validate_and_cast_params(params: dict) -> dict:
    """Проверяет и приводит значения params по KeyDataTypes.
       Неизвестные ключи — считаются string.
    """
    key_types = {k.name: k.type_of for k in KeyDataTypes.objects.all()}
    validated = {}

    for key, value in params.items():
        type_name = key_types.get(key, "string")
        validated[key] = cast_param_value(value, type_name)

    return validated
