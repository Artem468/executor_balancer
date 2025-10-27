from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from dispatcher.serializer import DispatchSerializer
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