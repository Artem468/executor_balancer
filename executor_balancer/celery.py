import os
import traceback
from celery import Celery
from celery.signals import worker_process_init
from django.conf import settings
from mongoengine import disconnect, connect

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'executor_balancer.settings')
app = Celery('executor_balancer')

app.conf.update(
    task_routes={
        'dispatcher.tasks.dispatch_request': {'queue': 'dispatch_queue'},
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    task_track_started=True,
    task_compression='gzip',
    result_compression='gzip',
    task_soft_time_limit=30,
    worker_max_memory_per_child=150000,
    broker_transport_options={'visibility_timeout': 43200}
)

app.config_from_object('django.conf:settings', namespace='CELERY')
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