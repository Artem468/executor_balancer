import datetime
import time

import redis
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse
from mongoengine import DoesNotExist
from pymongo import MongoClient
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response

from core.models import User, Request
from core.serializers import UserSerializer, RequestSerializer
from executor_balancer.celery import app

START_TIME = datetime.datetime.now(datetime.UTC)


class HealthCheckView(APIView):
    """
    DRF health-check endpoint.
    Проверяет состояние:
    - Django
    - MongoDB
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
            mongo_uri = (
                f"mongodb://{settings.MONGO_USER}:{settings.MONGO_PASS}@"
                f"{settings.MONGO_HOST}:{settings.MONGO_PORT}/"
                f"{settings.MONGO_DB}"
            )
            client = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=2000,
                authSource="admin",
            )
            client.admin.command("ping")
            latency = round((time.time() - start) * 1000, 2)
            results["mongodb"] = {"status": "ok", "latency_ms": latency}
            client.close()
        except Exception as e:
            results["mongodb"] = {"status": f"error: {e}"}

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


@extend_schema(tags=["Пользователи"])
class UserViewSet(viewsets.ViewSet):
    """CRUD для пользователей."""

    @extend_schema(
        summary="Список пользователей",
        description="Возвращает список всех пользователей системы.",
        responses={200: UserSerializer(many=True)},
    )
    def list(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Получить пользователя по ID",
        description="Возвращает информацию о конкретном пользователе по его ID.",
        responses={
            200: UserSerializer,
            404: OpenApiResponse(description="Пользователь не найден"),
        },
    )
    def retrieve(self, request, pk=None):
        try:
            user = User.objects.get(id=pk)
        except DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=404)
        return Response(UserSerializer(user).data)

    @extend_schema(
        summary="Создать пользователя",
        description="Создаёт нового пользователя в системе.",
        request=UserSerializer,
        responses={
            201: UserSerializer,
            400: OpenApiResponse(description="Ошибка валидации"),
        },
    )
    def create(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data, status=201)
        return Response(serializer.errors, status=400)

    @extend_schema(
        summary="Обновить пользователя",
        description="Частично обновляет данные пользователя.",
        request=UserSerializer,
        responses={
            200: UserSerializer,
            404: OpenApiResponse(description="Пользователь не найден"),
        },
    )
    def update(self, request, pk=None):
        try:
            user = User.objects.get(id=pk)
        except DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=404)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data)
        return Response(serializer.errors, status=400)

    @extend_schema(
        summary="Удалить пользователя",
        description="Удаляет пользователя по ID.",
        responses={
            204: OpenApiResponse(description="Пользователь удалён"),
            404: OpenApiResponse(description="Пользователь не найден"),
        },
    )
    def destroy(self, request, pk=None):
        try:
            user = User.objects.get(id=pk)
        except DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=404)
        user.delete()
        return Response(status=204)


@extend_schema(tags=["Заявки"])
class RequestViewSet(viewsets.ViewSet):
    """CRUD для заявок."""

    @extend_schema(
        summary="Список заявок",
        description="Возвращает список всех заявок в системе.",
        responses={200: RequestSerializer(many=True)},
    )
    def list(self, request):
        items = Request.objects.all()
        serializer = RequestSerializer(items, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Получить заявку по ID",
        description="Возвращает данные конкретной заявки по ID.",
        responses={
            200: RequestSerializer,
            404: OpenApiResponse(description="Заявка не найдена"),
        },
    )
    def retrieve(self, request, pk=None):
        try:
            item = Request.objects.get(id=pk)
        except DoesNotExist:
            return Response({"error": "Заявка не найдена"}, status=404)
        return Response(RequestSerializer(item).data)

    @extend_schema(
        summary="Создать заявку",
        description="Создаёт новую заявку в системе.",
        request=RequestSerializer,
        responses={
            201: RequestSerializer,
            400: OpenApiResponse(description="Ошибка валидации"),
        },
    )
    def create(self, request):
        serializer = RequestSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(RequestSerializer(obj).data, status=201)
        return Response(serializer.errors, status=400)

    @extend_schema(
        summary="Обновить заявку",
        description="Частично обновляет поля заявки.",
        request=RequestSerializer,
        responses={
            200: RequestSerializer,
            404: OpenApiResponse(description="Заявка не найдена"),
        },
    )
    def update(self, request, pk=None):
        try:
            item = Request.objects.get(id=pk)
        except DoesNotExist:
            return Response({"error": "Заявка не найдена"}, status=404)
        serializer = RequestSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(RequestSerializer(obj).data)
        return Response(serializer.errors, status=400)

    @extend_schema(
        summary="Удалить заявку",
        description="Удаляет заявку по ID.",
        responses={
            204: OpenApiResponse(description="Заявка удалена"),
            404: OpenApiResponse(description="Заявка не найдена"),
        },
    )
    def destroy(self, request, pk=None):
        try:
            item = Request.objects.get(id=pk)
        except DoesNotExist:
            return Response({"error": "Заявка не найдена"}, status=404)
        item.delete()
        return Response(status=204)