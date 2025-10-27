import datetime

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from mongoengine import connect, disconnect

from dispatcher.models import DispatchLogs
from core.models import Request, User

THRESHOLD_PERCENT = 0.05

@shared_task(bind=True)
def dispatch_request(self, data):
    """
    Функция распределения заявок
    """
    try:
        disconnect(alias="default")
    except Exception:
        pass

    connect(
        db=settings.MONGO_DB,
        host=f"mongodb://{settings.MONGO_USER}:{settings.MONGO_PASS}@{settings.MONGO_HOST}:{settings.MONGO_PORT}/",
        authentication_source="admin",
    )

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

    user_counts = {
        doc["_id"]: doc["daily_count"] for doc in Request.objects.aggregate(*pipeline)
    }

    heights = []
    for user in User.objects.only("id", "params", "max_daily_requests"):
        daily_count = user_counts.get(user.id, 0)
        if (
            user.max_daily_requests is not None
            and daily_count >= user.max_daily_requests
        ):
            continue

        height = sum(
            (v[1] if isinstance(v, (list, tuple)) and len(v) > 1 else 1)
            for k, v in req_params.items()
            if user.params.get(k) == v[0]
        )

        heights.append({"id": user.id, "height": height, "daily_count": daily_count})

    if not heights:
        return {"status": "no suitable users"}

    max_height = max(heights, key=lambda h: h["height"])

    candidates = [
        h for h in heights if max_height["height"] - h["height"] <= max_height["height"] * THRESHOLD_PERCENT
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
            "user_id": user_obj.username,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        },
    )

    return {"assigned_user": str(user_id)}