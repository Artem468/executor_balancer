from rest_framework import serializers


class DispatchSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)
    parent_id = serializers.IntegerField(required=True, allow_null=True)
    status = serializers.CharField(required=True)
    params = serializers.JSONField(required=True)
    updated_at = serializers.DateTimeField(required=True)
    created_at = serializers.DateTimeField(required=True)
