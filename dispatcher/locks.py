from typing import Dict
from django.core.cache import cache
import datetime
import time


class RequestCounter:
    """Класс для подсчета количества запросов"""
    COUNTS_CACHE_KEY = "daily_request_counts"
    COUNTS_CACHE_TIMEOUT = 24 * 60 * 60
    UPDATE_INTERVAL = 60
    _last_db_update = 0

    @classmethod
    def get_counts_from_db(cls) -> Dict[str, int]:
        """Считает количество запросов за день из базы данных"""
        from core.models import Request
        
        today = datetime.date.today()
        today_start = datetime.datetime.combine(today, datetime.time.min).replace(
            tzinfo=datetime.timezone.utc
        )

        pipeline = [
            {
                "$match": {
                    "status": "accept",
                    "created_at": {"$gte": today_start}
                }
            },
            {
                "$group": {
                    "_id": "$user",
                    "count": {"$sum": 1}
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "count": 1
                }
            }
        ]

        counts = {}
        for result in Request.objects.aggregate(pipeline, allowDiskUse=True):
            counts[str(result["_id"])] = result["count"]
        return counts

    @classmethod
    def get_request_counts(cls, force_db_read: bool = False) -> Dict[str, int]:
        current_time = time.time()

        if not force_db_read:
            counts = cache.get(cls.COUNTS_CACHE_KEY)
            if counts is not None and (current_time - cls._last_db_update) < cls.UPDATE_INTERVAL:
                return counts

        counts = cls.get_counts_from_db()
        cache.set(cls.COUNTS_CACHE_KEY, counts, cls.COUNTS_CACHE_TIMEOUT)
        cls._last_db_update = current_time
        return counts

    @classmethod
    def increment_count(cls, user_id: str) -> None:
        counts = cls.get_request_counts()
        counts[user_id] = counts.get(user_id, 0) + 1
        cache.set(cls.COUNTS_CACHE_KEY, counts, cls.COUNTS_CACHE_TIMEOUT)