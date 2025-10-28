import datetime
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from mongoengine import connect, disconnect

from dispatcher.models import DispatchLogs
from core.models import Request, User

THRESHOLD_PERCENT = 0.05


def match_param(user_value, req_value, operator="EQ"):
    """Проверяет соответствие одного параметра пользователя и заявки по оператору."""
    if user_value is None:
        return False
    if operator == "EQ":
        return user_value == req_value
    elif operator == "NE":
        return user_value != req_value
    elif operator == "GT":
        return user_value > req_value
    elif operator == "GTE":
        return user_value >= req_value
    elif operator == "LT":
        return user_value < req_value
    elif operator == "LTE":
        return user_value <= req_value
    elif operator == "ICONTAINS":
        if not isinstance(user_value, str) or not isinstance(req_value, str):
            return False
        return req_value.lower() in user_value.lower()
    return False


@shared_task(bind=True, max_retries=None, default_retry_delay=300)
def dispatch_request(self, data):
    """Распределение заявки с учётом value, operator и веса (height)."""

    req_id = data.get("id")
    if not req_id:
        return {"error": "request_id not provided"}

    request_obj = Request.objects(id=req_id).first()
    if not request_obj:
        return {"error": f"Request {req_id} not found"}

    req_parent_id = request_obj.parent.id if request_obj.parent else None
    req_params = request_obj.params or {}
    req_created_at = request_obj.created_at
    req_updated_at = request_obj.updated_at

    now = datetime.datetime.now(datetime.UTC)

    pipeline = [
        {"$match": {"status": "processed", "created_at": {"$gte": now}}},
        {"$group": {"_id": "$user", "daily_count": {"$sum": 1}}},
    ]
    user_counts = {doc["_id"]: doc["daily_count"] for doc in Request.objects.aggregate(*pipeline)}

    heights = []
    for user in User.objects.only("id", "params", "max_daily_requests"):
        daily_count = user_counts.get(user.id, 0)
        if user.max_daily_requests is not None and daily_count >= user.max_daily_requests:
            continue

        total_height = 0
        for key, param in req_params.items():
            if not isinstance(param, dict):
                continue
            req_value = param.get("value")
            operator = param.get("operator", "EQ")
            weight = float(param.get("height", 1.0))

            user_value = user.params.get(key)
            if match_param(user_value, req_value, operator):
                total_height += weight

        if total_height > 0:
            heights.append({
                "id": user.id,
                "height": total_height,
                "daily_count": daily_count
            })

    if not heights:
        raise self.retry(countdown=60)

    max_height = max(heights, key=lambda h: h["height"])["height"]
    candidates = [
        h for h in heights if max_height - h["height"] <= max_height * THRESHOLD_PERCENT
    ]
    most_relevant_user = min(candidates, key=lambda h: h["daily_count"])

    user_id = most_relevant_user["id"]
    user_obj = User.objects(id=user_id).first()
    Request.objects(id=req_id).update(set__user=user_obj)

    DispatchLogs(
        request_id=req_id,
        parent_id=req_parent_id,
        task_id=self.request.id,
        request_created_at=req_created_at,
        request_updated_at=req_updated_at,
    ).save()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "dispatched",
        {
            "type": "request_dispatched",
            "request_id": req_id,
            "user": user_obj.username,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        },
    )

    return {"assigned_user": str(user_id)}
