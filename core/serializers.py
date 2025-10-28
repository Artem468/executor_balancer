from django.core.exceptions import ValidationError
from rest_framework import serializers

from core.models import User, Request, KeyDataTypes
from core.utils import validate_and_cast_params, cast_params


class UserSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    params = serializers.DictField(required=False)
    max_daily_requests = serializers.IntegerField(required=False, allow_null=True)

    def validate_params(self, value):
        """Автоматически привести типы из KeyDataTypes"""
        try:
            return cast_params(value)
        except ValidationError as e:
            raise serializers.ValidationError(str(e))

    def create(self, validated_data):
        user = User(**validated_data)
        user.save()
        return user

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance


class RequestSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    user = serializers.CharField(required=False, allow_null=True, read_only=True)
    parent = serializers.CharField(required=False, allow_null=True)
    params = serializers.DictField(required=False)
    text = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        required=False,
        choices=[
            ("processed", "Processed"),
            ("await", "Await"),
            ("accept", "Accept"),
            ("reject", "Reject"),
        ],
    )
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def validate_params(self, value):
        """Автоматически привести типы из KeyDataTypes"""
        try:
            return validate_and_cast_params(value)
        except ValidationError as e:
            raise serializers.ValidationError(str(e))

    def create(self, validated_data):
        return Request(**validated_data).save()

    def update(self, instance, validated_data):
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        return instance


class KeyDataTypesSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(required=True)
    type_of = serializers.ChoiceField(
        choices=["string", "integer", "float", "boolean", "datetime"],
        default="string"
    )

    def create(self, validated_data):
        return KeyDataTypes(**validated_data).save()

    def update(self, instance, validated_data):
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        return instance
