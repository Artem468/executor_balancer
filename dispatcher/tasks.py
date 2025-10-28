import datetime
import uuid
from typing import Dict, List, Optional

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer

from core.models import Request, User
from dispatcher.models import DispatchLogs
from .scoring import UserScorer, LoadBalancer


class CandidateInfo:
    def __init__(
        self,
        user_id: str,
        total_score: float,
        max_score: float,
        daily_requests: int,
        max_daily_requests: Optional[int],
    ):
        self.user_id = user_id
        self.total_score = total_score
        self.max_score = max_score
        self.daily_requests = daily_requests
        self.max_daily_requests = max_daily_requests
        self.load_factor = LoadBalancer.calculate_load_factor(
            daily_requests, max_daily_requests, total_score, max_score
        )

    def __lt__(self, other):
        return self.load_factor < other.load_factor


def get_daily_request_counts() -> Dict[str, int]:
    """Получает количество заявок за день для каждого пользователя"""
    today = datetime.date.today()
    today_start = datetime.datetime.combine(today, datetime.time.min).replace(
        tzinfo=datetime.timezone.utc
    )

    pipeline = [
        {"$match": {"status": "accept", "created_at": {"$gte": today_start}}},
        {"$group": {"_id": "$user", "count": {"$sum": 1}}},
    ]

    counts = {}
    for result in Request.objects.aggregate(*pipeline):
        counts[str(result["_id"])] = result["count"]
    return counts


@shared_task(bind=True, max_retries=None, default_retry_delay=300)
def dispatch_request(
    self, request_id: str, min_score_fraction: float = 0.7
) -> Optional[str]:
    """Распределяет заявку между пользователями с учетом их параметров и нагрузки"""

    try:
        request = Request.objects.get(id=request_id)
    except Request.DoesNotExist:
        return None

    request_params = request.params or {}

    scorer = UserScorer(min_score_fraction=min_score_fraction)
    daily_counts = get_daily_request_counts()

    candidates: List[CandidateInfo] = []

    for user in User.objects.all():
        parameter_scores = scorer.calculate_parameter_scores(
            user.params or {}, request_params
        )
        total_score, max_possible_score = scorer.calculate_total_score(parameter_scores)

        if not scorer.is_suitable_candidate(total_score, max_possible_score):
            continue

        daily_requests = daily_counts.get(str(user.id), 0)

        if user.max_daily_requests and daily_requests >= user.max_daily_requests:
            continue

        candidates.append(
            CandidateInfo(
                str(user.id),
                total_score,
                max_possible_score,
                daily_requests,
                user.max_daily_requests,
            )
        )

    if not candidates:
        fallback_candidates = []
        for user in User.objects.all():
            daily_requests = daily_counts.get(str(user.id), 0)

            if user.max_daily_requests and daily_requests >= user.max_daily_requests:
                continue

            fallback_candidates.append(
                UserScorer.create_fallback_candidate(
                    str(user.id), daily_requests, user.max_daily_requests
                )
            )

        if not fallback_candidates:
            return None

        best_candidate = min(fallback_candidates)
    else:
        best_candidate = min(candidates)

    best_user_id = best_candidate.user_id

    best_user = User.objects.get(id=best_user_id)

    request.user = best_user
    request.updated_at = datetime.datetime.now(datetime.UTC)
    request.save()

    parent_id = str(request.parent.id) if request.parent else None
    DispatchLogs.objects.create(
        request_id=str(request.id),
        task_id=uuid.UUID(self.request.id),
        parent_id=parent_id,
        request_created_at=request.created_at,
        request_updated_at=request.updated_at,
    )

    # print(
    #     {
    #         "total_candidates": len(candidates),
    #         "chosen_candidate": {
    #             "user_id": str(best_user_id),
    #             "daily_requests": best_candidate.daily_requests,
    #             "score": best_candidate.total_score,
    #             "max_score": best_candidate.max_score,
    #             "load_factor": best_candidate.load_factor,
    #         },
    #     }
    # )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "dispatched",
        {
            "type": "request_dispatched",
            "request_id": str(request.id),
            "user": str(best_user_id),
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        },
    )

    return str(best_user_id)