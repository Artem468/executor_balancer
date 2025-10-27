from mongoengine import (
    Document,
    StringField,
    DictField,
    IntField,
    ReferenceField,
    DateTimeField,
    CASCADE,
)
import datetime


class User(Document):
    """
    Пользователь системы.
    """
    username = StringField(required=True, unique=True, verbose_name="Имя пользователя")
    password = StringField(required=True, verbose_name="Пароль")
    email = StringField(required=False, verbose_name="Email")
    first_name = StringField(required=False, verbose_name="Имя")
    last_name = StringField(required=False, verbose_name="Фамилия")

    params = DictField(default=dict, verbose_name="Параметры")
    max_daily_requests = IntField(default=None, null=True, verbose_name="Максимальное количество заявок")

    meta = {
        "collection": "user",
        "ordering": ["username"],
        "verbose_name": "Пользователь",
        "verbose_name_plural": "Пользователи",
    }

    def __str__(self):
        return self.username


class Request(Document):
    """
    Модель заявки.
    """
    STATUS_CHOICES = ("processed", "await", "accept", "reject")

    parent = ReferenceField("self", reverse_delete_rule=CASCADE, null=True, verbose_name="Родитель")
    user = ReferenceField(User, null=True, verbose_name="Пользователь")

    params = DictField(default=dict, verbose_name="Параметры")
    text = StringField(null=True, verbose_name="Описание")

    status = StringField(
        choices=STATUS_CHOICES,
        default="processed",
        required=True,
        verbose_name="Статус",
    )

    created_at = DateTimeField(default=datetime.datetime.now(datetime.UTC), verbose_name="Создано")
    updated_at = DateTimeField(default=datetime.datetime.now(datetime.UTC), verbose_name="Обновлено")

    meta = {
        "collection": "request",
        "ordering": ["-created_at"],
        "verbose_name": "Заявка",
        "verbose_name_plural": "Заявки",
    }

    def save(self, *args, **kwargs):
        """Обновляем время модификации при сохранении."""
        self.updated_at = datetime.datetime.now(datetime.UTC)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"#{self.id} | {self.status}"
