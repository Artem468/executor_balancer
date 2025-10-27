import datetime
from celery import shared_task

from dispatcher.models import DispatchLogs
from core.models import  Request, User


@shared_task(bind=True)
def dispatch_request(self, data):
    """
    Функция распределения заявок
    """

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

    users = User.objects.only("id", "params", "maxDailyRequests")

    now = datetime.datetime.now(datetime.UTC)

    heights = []

    for user in users:
        daily_count = Request.objects(
            user=user,
            status="processed",
            created_at__gte=now.replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()

        if user.maxDailyRequests is not None and daily_count >= user.maxDailyRequests:
            continue

        height = 0
        for k, v in req_params.items():
            if user.params.get(k) == v[0]:
                height += v[1] if isinstance(v, (list, tuple)) and len(v) > 1 else 1

        heights.append({"id": user.id, "height": height})

    if not heights:
        DispatchLogs(
            request_id=req_id,
            parent_id=req_parent_id,
            task_id=self.request.id,
            request_created_at=req_created_at,
            request_updated_at=req_updated_at,
        ).save()
        return {"status": "no suitable users"}

    most_relevant_user = max(heights, key=lambda h: h["height"])
    user_id = most_relevant_user["id"]

    request_obj.user = User.objects(id=user_id).first()
    request_obj.status = "assigned"
    request_obj.save()

    DispatchLogs(
        request_id=req_id,
        parent_id=req_parent_id,
        task_id=self.request.id,
        request_created_at=req_created_at,
        request_updated_at=req_updated_at,
    ).save()

    return {"assigned_user": int(user_id)}