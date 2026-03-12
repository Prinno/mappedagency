import re

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, DataCollectionRecord


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "phone_number",
            "national_id",
            "role",
            "position",
            "daily_target",
            "created_at",
            "updated_at",
            "is_active",
        ]
        # Users can update their own basic profile details (name, email, phone),
        # but not security / permission fields like role or is_active.
        read_only_fields = ["id", "role", "created_at", "updated_at", "is_active"]


class ManagerCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "phone_number",
            "password",
            "position",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.role = User.Role.MANAGER
        user.set_password(password)
        user.is_active = True
        user.save()
        return user


class DataCollectorCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    national_id = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "phone_number",
            "national_id",
            "password",
            "daily_target",
        ]

    def validate_national_id(self, value: str) -> str:
        """Validate national ID in the format 00000000-00000-00000-00."""

        value = value.strip()
        pattern = re.compile(r"^\d{8}-\d{5}-\d{5}-\d{2}$")
        if not pattern.match(value):
            raise serializers.ValidationError(
                "National ID must be in the format 00000000-00000-00000-00"
            )
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        manager = request.user if request else None
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.role = User.Role.DATA_COLLECTOR
        user.manager = manager
        user.set_password(password)
        user.is_active = True
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Login with email or phone + password, returning JWT tokens."""

    identifier = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier")
        password = attrs.get("password")

        user = None

        # Try email first if identifier looks like an email
        if "@" in identifier:
            try:
                user = User.objects.get(email__iexact=identifier)
            except User.DoesNotExist:
                user = None
        else:
            # Otherwise treat identifier as phone number
            try:
                user = User.objects.get(phone_number=identifier)
            except User.DoesNotExist:
                user = None

        if user is None or not user.check_password(password) or not user.is_active:
            raise serializers.ValidationError({"non_field_errors": ["Invalid credentials"]})

        # Generate JWT tokens for the authenticated user
        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user).data,
        }


class DataCollectionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataCollectionRecord
        fields = [
            "id",
            "collector",
            "agent_name",
            "agent_till_number",
            "status",
            "rejection_reason",
            "latitude",
            "longitude",
            "title",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "collector"]


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer used by authenticated users to change their own password."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        new_password = self.validated_data["new_password"]
        user.set_password(new_password)
        user.save()
        return user


class DataCollectorStatusSerializer(serializers.ModelSerializer):
    """Serializer for managers to update collector status/target."""

    class Meta:
        model = User
        fields = ["is_active", "daily_target"]


class DataCollectorPasswordResetSerializer(serializers.Serializer):
    """Serializer used by managers to reset a collector's password."""

    new_password = serializers.CharField(write_only=True, min_length=8)

    def save(self, **kwargs):
        collector: User = self.context["collector"]
        new_password = self.validated_data["new_password"]
        collector.set_password(new_password)
        collector.save()
        return collector
