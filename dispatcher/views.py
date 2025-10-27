from datetime import date

from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from dispatcher.serializer import DispatchSerializer, DailySummaryQuerySerializer
from .models import DispatchLogs
from .tasks import dispatch_request


class DispatcherView(APIView):
    @extend_schema(
        tags=["Распределение"],
        summary="Распределитель",
        description="Получает данные заявки для распределения, решает какой юзер более релевантен",
        request=DispatchSerializer,
        responses={200: {"status": "string", "message": "string"}},
    )
    def post(self, request):
        serializer = DispatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        task = dispatch_request.delay(request.data)
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)


class DailySummaryView(APIView):
    """
    API вью для получения суммарной выгрузки заявок по дням.
    Поддерживает query-параметры: start_date и end_date в формате YYYY-MM-DD.
    """

    @extend_schema(
        tags=["Распределение"],
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=str,
                description="Начальная дата в формате YYYY-MM-DD (опционально)",
                required=False,
            ),
            OpenApiParameter(
                name="end_date",
                type=str,
                description="Конечная дата в формате YYYY-MM-DD (опционально)",
                required=False,
            ),
        ],
        responses={
            200: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "format": "date"},
                        "count": {"type": "integer"},
                    },
                },
                "description": "Список с суммой заявок по дням",
            },
            400: {
                "type": "object",
                "properties": {
                    "error": {"type": "string"},
                },
                "description": "Ошибка в формате даты",
            },
        },
        summary="Получить суммарную выгрузку заявок по дням",
        description="Возвращает количество заявок, сгруппированных по дням. Можно фильтровать по диапазону дат.",
    )
    def get(self, request):
        serializer = DailySummaryQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        start_date = serializer.validated_data.get("start_date")
        end_date = serializer.validated_data.get("end_date")

        summary = DispatchLogs.daily_summary(start_date=start_date, end_date=end_date)
        return Response(summary)