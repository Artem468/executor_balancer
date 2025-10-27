import datetime
import uuid

from mongoengine import (
    Document,
    StringField,
    UUIDField,
    DateTimeField,
)


class DispatchLogs(Document):
    """
    Логи выполнения задач (аналог Django модели, но для MongoDB).
    """

    request_id = StringField(required=True)
    task_id = UUIDField(binary=False, default=uuid.uuid4)
    parent_id = StringField(null=True)
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

    @classmethod
    def daily_summary(cls, start_date=None, end_date=None):
        """
        Возвращает агрегированные данные: сумму (количество) заявок по дням.
        Группирует по request_created_at (по дням в формате YYYY-MM-DD).
        Опционально фильтрует по start_date и end_date (datetime.date объекты).

        Возвращает список словарей: [{'date': 'YYYY-MM-DD', 'count': N}, ...]
        """
        pipeline = []

        match_stage = {}
        if start_date:
            match_stage["$gte"] = datetime.datetime.combine(
                start_date, datetime.time.min
            )
        if end_date:
            match_stage["$lte"] = datetime.datetime.combine(end_date, datetime.time.max)
        if match_stage:
            pipeline.append({"$match": {"request_created_at": match_stage}})

        pipeline.extend(
            [
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$request_created_at",
                            }
                        },
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )

        results = list(cls.objects.aggregate(*pipeline))

        for item in results:
            item['date'] = item.pop('_id')

        return results