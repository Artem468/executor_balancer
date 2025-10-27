import datetime
import uuid

from mongoengine import (
    Document,
    IntField,
    UUIDField,
    DateTimeField,
)


class DispatchLogs(Document):
    """
    Логи выполнения задач (аналог Django модели, но для MongoDB).
    """

    request_id = IntField(required=True)
    task_id = UUIDField(binary=False, default=uuid.uuid4)
    parent_id = IntField(null=True)
    request_created_at = DateTimeField(default=datetime.datetime.now(datetime.UTC))
    request_updated_at = DateTimeField(default=datetime.datetime.now(datetime.UTC))

    meta = {
        "collection": "dispatch_logs",
        "ordering": ["-request_created_at"],
        "verbose_name": "Лог отправки",
        "verbose_name_plural": "Логи отправок",
    }

    def save(self, *args, **kwargs):
        """Обновляем время модификации при сохранении."""
        self.request_updated_at = datetime.datetime.now(datetime.UTC)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.task_id}] Request {self.request_id}"
