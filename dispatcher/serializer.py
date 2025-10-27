from rest_framework import serializers


class DispatchSerializer(serializers.Serializer):
    id = serializers.CharField(required=True)
    parent_id = serializers.CharField(required=True, allow_null=True)
    params = serializers.JSONField(required=True)
    updated_at = serializers.DateTimeField(required=True)
    created_at = serializers.DateTimeField(required=True)


class DailySummaryQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False, help_text="Начальная дата в формате YYYY-MM-DD")
    end_date = serializers.DateField(required=False, help_text="Конечная дата в формате YYYY-MM-DD")