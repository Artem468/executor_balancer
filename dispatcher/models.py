import uuid

from django.db import models


class DispatchLogs(models.Model):
    request_id = models.IntegerField()
    task_id = models.UUIDField(default=uuid.uuid4)
    parent_id = models.IntegerField(null=True, blank=True)
    request_created_at = models.DateTimeField(auto_now_add=True)
    request_updated_at = models.DateTimeField(auto_now=True)
