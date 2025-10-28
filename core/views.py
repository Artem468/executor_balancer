import datetime
import time

import redis
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from mongoengine import DoesNotExist
from pymongo import MongoClient
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import User, Request, KeyDataTypes
from core.serializers import UserSerializer, RequestSerializer, KeyDataTypesSerializer
from dispatcher.tasks import dispatch_request
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

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "new_requests",
                {
                    "type": "new_request",
                    "id": str(obj.id),
                    "status": obj.status,
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                },
            )

            _ = dispatch_request.delay({"id": str(obj.id)})

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


@extend_schema(tags=["Типы данных"])
class KeyDataTypesViewSet(viewsets.ViewSet):
    """
    CRUD для типов данных ключей
    """

    @extend_schema(
        summary="Получить список типов данных",
        description="Возвращает все доступные типы данных ключей.",
        responses={200: KeyDataTypesSerializer(many=True)},
    )
    def list(self, request):
        objs = KeyDataTypes.objects.all()
        serializer = KeyDataTypesSerializer(objs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Получить конкретный тип данных",
        description="Возвращает информацию о типе данных по его ID.",
        responses={
            200: KeyDataTypesSerializer,
            404: OpenApiResponse(description="Тип данных не найден"),
        },
    )
    def retrieve(self, request, pk=None):
        try:
            obj = KeyDataTypes.objects.get(id=pk)
        except KeyDataTypes.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        serializer = KeyDataTypesSerializer(obj)
        return Response(serializer.data)

    @extend_schema(
        summary="Создать тип данных",
        description="Создаёт новый тип данных для ключей параметров.",
        request=KeyDataTypesSerializer,
        responses={
            201: KeyDataTypesSerializer,
            400: OpenApiResponse(description="Ошибка валидации"),
        },
    )
    def create(self, request):
        serializer = KeyDataTypesSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(KeyDataTypesSerializer(obj).data, status=201)
        return Response(serializer.errors, status=400)

    @extend_schema(
        summary="Обновить тип данных",
        description="Обновляет запись типа данных по ID.",
        request=KeyDataTypesSerializer,
        responses={
            200: KeyDataTypesSerializer,
            400: OpenApiResponse(description="Ошибка валидации"),
            404: OpenApiResponse(description="Тип данных не найден"),
        },
    )
    def update(self, request, pk=None):
        try:
            item = KeyDataTypes.objects.get(id=pk)
        except DoesNotExist:
            return Response({"error": "Заявка не найдена"}, status=404)
        serializer = KeyDataTypesSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(KeyDataTypesSerializer(obj).data)
        return Response(serializer.errors, status=400)

    @extend_schema(
        summary="Удалить тип данных",
        description="Удаляет тип данных по ID.",
        responses={
            204: OpenApiResponse(description="Успешное удаление"),
            404: OpenApiResponse(description="Тип данных не найден"),
        },
    )
    def destroy(self, request, pk=None):
        try:
            obj = KeyDataTypes.objects.get(id=pk)
        except KeyDataTypes.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        obj.delete()
        return Response(status=204)


@extend_schema(
    tags=["Заявки"],
    parameters=[
        OpenApiParameter(
            name="period",
            description="Период: 'week' или 'month'",
            required=True,
            type=str,
            enum=["week", "month"],
        )
    ],
)
class RequestStatsAPIView(APIView):
    """
    Возвращает статистику заказов за период.
    GET-параметр:
      - period: "week" или "month"
    """

    def get(self, request):
        period = request.GET.get("period", "week")
        now = datetime.datetime.now(datetime.UTC)

        if period == "week":
            days = 7
        elif period == "month":
            days = 30
        else:
            return Response(
                {"error": "period должен быть 'week' или 'month'"}, status=400
            )

        start_date = now - datetime.timedelta(days=days - 1)

        qs = Request.objects(created_at__gte=start_date, created_at__lte=now)

        total_requests = qs.count()
        processed_requests = qs(status="processed", user__ne=None).count()
        accepted_requests = qs(status="accept").count()
        rejected_requests = qs(status="reject").count()
        awaited_requests = qs(status="await").count()

        performers_stats = qs(user__ne=None).distinct("user")
        max_requests = 0
        min_requests = 0
        if performers_stats:
            counts_per_user = [qs(user=u).count() for u in performers_stats]
            max_requests = max(counts_per_user)
            min_requests = min(counts_per_user)
        error = round((max_requests / min_requests) if min_requests else 0, 2)

        date_list = [start_date + datetime.timedelta(days=i) for i in range(days)]
        counts_per_day = {}
        for d in date_list:
            day_start = datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.UTC)
            day_end = day_start + datetime.timedelta(days=1)
            counts_per_day[d.date()] = qs(
                created_at__gte=day_start, created_at__lt=day_end
            ).count()

        if period == "week":
            labels = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
            values = [counts_per_day.get(d.date(), 0) for d in date_list]
        else:
            labels = [d.strftime("%d.%m") for d in date_list]
            values = [counts_per_day.get(d.date(), 0) for d in date_list]

        chart = {"labels": labels, "values": values}

        data = {
            "stats": {
                "totalRequests": total_requests,
                "processedRequests": processed_requests,
                "acceptedRequests": accepted_requests,
                "rejectedRequests": rejected_requests,
                "awaitedRequests": awaited_requests,
                "performers": len(performers_stats),
            },
            "chart": chart,
            "workload": {
                "max": max_requests,
                "min": min_requests,
                "error": error,
            },
        }

        return Response(data)
