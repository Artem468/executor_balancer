import datetime
import time

import psycopg2
import redis
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from executor_balancer.celery import app

START_TIME = datetime.datetime.now(datetime.UTC)

class HealthCheckView(APIView):
    """
    DRF health-check endpoint.
    Проверяет состояние:
    - Django
    - PostgreSQL
    - Redis
    - RabbitMQ
    - Celery worker
    """

    authentication_classes = []
    permission_classes = []

    @extend_schema(
        tags=["Ядро"],
        summary="Health check",
        description="Возвращает статус доступа к api",
        responses={200: {"status": "string", "message": "string"}},
    )
    def get(self, request):
        results = {}

        now = datetime.datetime.now(datetime.UTC)
        uptime = now - START_TIME

        try:
            start = time.time()
            conn = psycopg2.connect(
                dbname=settings.DATABASES["default"]["NAME"],
                user=settings.DATABASES["default"]["USER"],
                password=settings.DATABASES["default"]["PASSWORD"],
                host=settings.DATABASES["default"]["HOST"],
                port=settings.DATABASES["default"]["PORT"],
                connect_timeout=2,
            )
            conn.close()
            results["postgres"] = {
                "status": "ok",
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            results["postgres"] = {"status": f"error: {e}"}

        try:
            start = time.time()
            redis_url = settings.CACHES["default"]["LOCATION"]
            client = redis.StrictRedis.from_url(redis_url)
            client.ping()
            results["redis"] = {
                "status": "ok",
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            results["redis"] = {"status": f"error: {e}"}

        try:
            start = time.time()
            with app.connection_for_read() as conn:
                conn.ensure_connection(max_retries=1)
            rabbitmq_latency = round((time.time() - start) * 1000, 2)
            results["rabbitmq"] = {"status": "ok", "latency_ms": rabbitmq_latency}
        except Exception as e:
            results["rabbitmq"] = {"status": f"error: {e}"}

        try:
            start = time.time()
            response = app.control.ping()
            if response:
                results["celery"] = {
                    "status": "ok",
                    "latency_ms": round((time.time() - start) * 1000, 2),
                }
            else:
                results["celery"] = {"status": "no response"}
        except Exception as e:
            results["celery"] = {"status": f"error: {e}"}

        all_ok = all(v.get("status") == "ok" for v in results.values())
        code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response(
            {
                "status": "ok" if all_ok else "degraded",
                "uptime": str(uptime).split(".")[0],
                "services": results,
            },
            status=code,
        )
