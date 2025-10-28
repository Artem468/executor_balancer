import datetime
import uuid
import logging
from typing import Dict, List, Optional

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer

from core.models import Request, User
from dispatcher.models import DispatchLogs
from .scoring import UserScorer
from .candidate_info import CandidateInfo
from .locks import RequestCounter

logger = logging.getLogger(__name__)


def find_available_users(request_params: Dict, min_score_fraction: float = 0.7) -> List[CandidateInfo]:
    """Находит доступных пользователей с учетом параметров и нагрузки"""
    scorer = UserScorer(min_score_fraction=min_score_fraction)
    daily_counts = RequestCounter.get_request_counts()
    candidates: List[CandidateInfo] = []
    
    for user in User.objects.only('id', 'max_daily_requests', 'params').all():
        daily_requests = daily_counts.get(str(user.id), 0)
        if user.max_daily_requests and daily_requests >= user.max_daily_requests:
            continue

        parameter_scores = scorer.calculate_parameter_scores(
            user.params or {}, request_params
        )
        total_score, max_possible_score = scorer.calculate_total_score(parameter_scores)
        is_fallback = not scorer.is_suitable_candidate(total_score, max_possible_score)
        
        candidates.append(
            CandidateInfo(
                str(user.id),
                total_score,
                max_possible_score,
                daily_requests,
                user.max_daily_requests,
                is_fallback=is_fallback
            )
        )
    return candidates


@shared_task(bind=True)
def dispatch_request(
    self, request_id: str, min_score_fraction: float = 0.7
) -> Optional[str]:
    """Распределяет заявку между пользователями с учетом их параметров и нагрузки"""
    try:
        request = Request.objects.get(id=request_id)
    except Request.DoesNotExist:
        logger.error(f"Request {request_id} not found")
        return None

    request_params = request.params or {}
    candidates = find_available_users(request_params, min_score_fraction)

    if not candidates:
        logger.error(f"No available users found for request {request_id}")
        return None

    primary_candidates = sorted([c for c in candidates if not c.is_fallback])
    fallback_candidates = sorted([c for c in candidates if c.is_fallback])
    best_candidate = primary_candidates[0] if primary_candidates else fallback_candidates[0]
    best_user_id = best_candidate.user_id

    try:
        best_user = User.objects.only('id').get(id=best_user_id)
    except User.DoesNotExist:
        logger.error(f"User {best_user_id} not found")
        return None

    request.user = best_user
    request.updated_at = datetime.datetime.now(datetime.UTC)
    request.save()

    RequestCounter.increment_count(str(best_user_id))

    parent_id = str(request.parent.id) if request.parent else None
    DispatchLogs.objects.create(
        request_id=str(request.id),
        task_id=uuid.UUID(self.request.id),
        parent_id=parent_id,
        request_created_at=request.created_at,
        request_updated_at=request.updated_at,
    )

    async_to_sync(get_channel_layer().group_send)(
        "dispatched",
        {
            "type": "request_dispatched",
            "request_id": str(request.id),
            "user": str(best_user_id),
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        },
    )

    return str(best_user_id)