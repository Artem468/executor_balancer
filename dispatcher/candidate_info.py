from typing import Optional
from .scoring import LoadBalancer


class CandidateInfo:
    def __init__(self, user_id: str, total_score: float, max_score: float, 
                 daily_requests: int, max_daily_requests: Optional[int], 
                 is_fallback: bool = False):
        self.user_id = user_id
        self.total_score = total_score
        self.max_score = max_score
        self.daily_requests = daily_requests
        self.max_daily_requests = max_daily_requests
        self.is_fallback = is_fallback

        if is_fallback:
            self.load_factor = LoadBalancer.get_fallback_load_factor(
                daily_requests, max_daily_requests
            )
        else:
            self.load_factor = LoadBalancer.calculate_load_factor(
                daily_requests, max_daily_requests, total_score, max_score
            )

    def __lt__(self, other):
        if self.is_fallback == other.is_fallback:
            return self.load_factor < other.load_factor
        return not self.is_fallback