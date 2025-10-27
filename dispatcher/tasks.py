import datetime
from celery import shared_task
from django.conf import settings
from mongoengine import connect, disconnect

from dispatcher.models import DispatchLogs
from core.models import Request, User


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

    users = User.objects.only("id", "params", "max_daily_requests")

    now = datetime.datetime.now(datetime.UTC)

    heights = []

    for user in users:
        daily_count = Request.objects(
            user=user,
            status="processed",
            created_at__gte=now.replace(hour=0, minute=0, second=0, microsecond=0),
        ).count()

        if (
            user.max_daily_requests is not None
            and daily_count >= user.max_daily_requests
        ):
            continue

        height = 0
        for k, v in req_params.items():
            if user.params.get(k) == v[0]:
                height += v[1] if isinstance(v, (list, tuple)) and len(v) > 1 else 1

        heights.append({"id": user.id, "height": height})

    if not heights:
        return {"status": "no suitable users"}

    most_relevant_user = max(heights, key=lambda h: h["height"])
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

    return {"assigned_user": str(user_id)}