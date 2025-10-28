import os
import traceback

from celery import Celery
from celery.signals import worker_process_init
from django.conf import settings
from mongoengine import disconnect, connect

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'executor_balancer.settings')

app = Celery('executor_balancer')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@worker_process_init.connect
def init_mongo(**kwargs):
    try:
        disconnect(alias="default")
        connect(
            db=settings.MONGO_DB,
            host=f"mongodb://{settings.MONGO_USER}:{settings.MONGO_PASS}@{settings.MONGO_HOST}:{settings.MONGO_PORT}/",
            alias="default",
            authentication_source="admin",
        )
    except Exception:
        print(traceback.format_exc())