import csv
import json

from datetime import datetime, time, timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken, TokenError

from .models import User, DataCollectionRecord
from .permissions import IsSuperAdmin, IsManager, IsDataCollector
from .serializers import (
    ChangePasswordSerializer,
    DataCollectorPasswordResetSerializer,
    DataCollectionRecordSerializer,
    DataCollectorCreateSerializer,
    DataCollectorStatusSerializer,
    LoginSerializer,
    ManagerCreateSerializer,
    UserSerializer,
)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({"detail": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    """Return and allow updating the authenticated user's profile."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ManagerListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.filter(role=User.Role.MANAGER)
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ManagerCreateSerializer
        return UserSerializer


class ManagerDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.filter(role=User.Role.MANAGER)
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class DataCollectorListCreateView(generics.ListCreateAPIView):
    serializer_class = DataCollectorCreateSerializer
    permission_classes = [IsAuthenticated, IsManager | IsSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.SUPER_ADMIN:
            return User.objects.filter(role=User.Role.DATA_COLLECTOR)
        if user.role == User.Role.MANAGER:
            return User.objects.filter(role=User.Role.DATA_COLLECTOR, manager=user)
        return User.objects.none()

    def get_serializer_class(self):
        if self.request.method == "GET":
            return UserSerializer
        return DataCollectorCreateSerializer


class DataCollectorDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.filter(role=User.Role.DATA_COLLECTOR)
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsManager | IsSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.SUPER_ADMIN:
            return User.objects.filter(role=User.Role.DATA_COLLECTOR)
        if user.role == User.Role.MANAGER:
            return User.objects.filter(role=User.Role.DATA_COLLECTOR, manager=user)
        return User.objects.none()


class DataCollectorStatusUpdateView(generics.UpdateAPIView):
    """Allow managers/super admins to update collector status/target."""

    serializer_class = DataCollectorStatusSerializer
    permission_classes = [IsAuthenticated, IsManager | IsSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.SUPER_ADMIN:
            return User.objects.filter(role=User.Role.DATA_COLLECTOR)
        if user.role == User.Role.MANAGER:
            return User.objects.filter(role=User.Role.DATA_COLLECTOR, manager=user)
        return User.objects.none()


class DataCollectionRecordListCreateView(generics.ListCreateAPIView):
    serializer_class = DataCollectionRecordSerializer
    permission_classes = [IsAuthenticated, IsDataCollector]

    def get_queryset(self):
        qs = DataCollectionRecord.objects.filter(collector=self.request.user)
        till = self.request.query_params.get("till")
        if till:
            qs = qs.filter(agent_till_number__icontains=till)
        return qs

    def perform_create(self, serializer):
        serializer.save(collector=self.request.user)


class DataCollectionRecordManagerListView(generics.ListAPIView):
    """List all agent surveys for managers and super admins."""

    serializer_class = DataCollectionRecordSerializer
    permission_classes = [IsAuthenticated, IsManager | IsSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.SUPER_ADMIN:
            return DataCollectionRecord.objects.select_related("collector", "collector__manager")
        if user.role == User.Role.MANAGER:
            return DataCollectionRecord.objects.filter(collector__manager=user).select_related(
                "collector", "collector__manager"
            )
        return DataCollectionRecord.objects.none()


class DataCollectionRecordDetailView(generics.RetrieveUpdateAPIView):
    """Allow managers/super admins to view and update survey status."""

    serializer_class = DataCollectionRecordSerializer
    permission_classes = [IsAuthenticated, IsManager | IsSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.SUPER_ADMIN:
            return DataCollectionRecord.objects.select_related("collector", "collector__manager")
        if user.role == User.Role.MANAGER:
            return DataCollectionRecord.objects.filter(collector__manager=user).select_related(
                "collector", "collector__manager"
            )
        return DataCollectionRecord.objects.none()


class DataCollectionRecordExportView(APIView):
    """Export survey records to a CSV file for managers and super admins."""

    # We still keep default DRF auth, but also allow token via query param
    permission_classes = [AllowAny]

    def _get_effective_user(self, request):
        """Resolve the user either from DRF auth or an `access` token query param."""
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return user

        token_str = request.query_params.get("access") or request.query_params.get("token")
        if not token_str:
            return None

        try:
            access = AccessToken(token_str)
        except TokenError:
            return None

        user_id = access.get("user_id")
        if not user_id:
            return None
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    def get_queryset(self, user):
        if user.role == User.Role.SUPER_ADMIN:
            return DataCollectionRecord.objects.select_related("collector", "collector__manager")
        if user.role == User.Role.MANAGER:
            return DataCollectionRecord.objects.filter(collector__manager=user).select_related(
                "collector", "collector__manager"
            )
        return DataCollectionRecord.objects.none()

    def get(self, request, *args, **kwargs):
        user = self._get_effective_user(request)
        if user is None:
            return Response({"detail": "Authentication credentials were not provided or invalid."}, status=status.HTTP_401_UNAUTHORIZED)
        if user.role not in (User.Role.MANAGER, User.Role.SUPER_ADMIN):
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)

        queryset = self.get_queryset(user)

        # --- Apply optional ORM-level filters (date & collector) -----------------------------
        query_params = request.query_params

        # Period-based filtering: ?period=day|week|month&date=YYYY-MM-DD
        period = query_params.get("period")
        date_str = query_params.get("date")
        start_date_str = query_params.get("start_date")
        end_date_str = query_params.get("end_date")

        def _parse_date(value: str):
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                return None

        date_filter_applied = False

        if period and date_str:
            base_date = _parse_date(date_str)
            if base_date is not None:
                if period == "day":
                    start_date = end_date = base_date
                elif period == "week":
                    # Monday as the first day of the week
                    start_date = base_date - timedelta(days=base_date.weekday())
                    end_date = start_date + timedelta(days=6)
                elif period == "month":
                    start_date = base_date.replace(day=1)
                    # Move to first day of next month then step back one day
                    if start_date.month == 12:
                        next_month = start_date.replace(year=start_date.year + 1, month=1, day=1)
                    else:
                        next_month = start_date.replace(month=start_date.month + 1, day=1)
                    end_date = next_month - timedelta(days=1)
                else:
                    start_date = end_date = None

                if start_date and end_date:
                    tz = timezone.get_current_timezone()
                    start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
                    end_dt = timezone.make_aware(datetime.combine(end_date, time.max), tz)
                    queryset = queryset.filter(created_at__range=(start_dt, end_dt))
                    date_filter_applied = True

        # Fallback explicit date range: ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
        if not date_filter_applied and (start_date_str or end_date_str):
            start_date = _parse_date(start_date_str) if start_date_str else None
            end_date = _parse_date(end_date_str) if end_date_str else None
            tz = timezone.get_current_timezone()
            if start_date:
                start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
                queryset = queryset.filter(created_at__gte=start_dt)
            if end_date:
                end_dt = timezone.make_aware(datetime.combine(end_date, time.max), tz)
                queryset = queryset.filter(created_at__lte=end_dt)

        # Filter by data collector: ?collector_id=<id>
        collector_id = query_params.get("collector_id")
        if collector_id:
            try:
                queryset = queryset.filter(collector_id=int(collector_id))
            except (TypeError, ValueError):
                # Ignore invalid collector id
                pass

        # Filter by agent status: ?status=pending|approved|rejected
        status_param = query_params.get("status")
        if status_param in {choice[0] for choice in DataCollectionRecord.Status.choices}:
            queryset = queryset.filter(status=status_param)

        # Extract question texts (for header labels) from the first available record
        question_texts = {}
        first_record = queryset.first()
        if first_record and first_record.description:
            try:
                payload = json.loads(first_record.description or "{}")
                for q in payload.get("questions", []):
                    number = q.get("number")
                    text = q.get("text") or ""
                    if isinstance(number, int) and text:
                        question_texts[number] = text
            except json.JSONDecodeError:
                pass

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"agent_surveys_{timestamp}.csv"

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)

        # Define CSV header
        question_headers = []
        for i in range(1, 20):
            text = question_texts.get(i, "")
            if text:
                question_headers.append(f"Q{i}: {text}")
            else:
                question_headers.append(f"Q{i}")
        header = [
            "Record ID",
            "Collector Name",
            "Collector Phone",
            "Manager Name",
            "Agent Name",
            "Agent Till Number",
            "Latitude",
            "Longitude",
            "Title",
            "Created At",
            "Country",
            "Region",
            "District",
            "Ward",
            "Street",
            *question_headers,
        ]
        writer.writerow(header)

        # Location filters are applied per-row since location lives in JSON payload
        location_filters = {}
        for key in ["country", "region", "district", "ward", "street"]:
            value = query_params.get(key)
            if value:
                location_filters[key] = value.strip().lower()

        for record in queryset:
            country = region = district = ward = street = ""
            answers_by_number = {}

            try:
                payload = json.loads(record.description or "{}")
                location = payload.get("location", {}) or {}
                country = location.get("country", "")
                region = location.get("region", "")
                district = location.get("district", "")
                ward = location.get("ward", "")
                street = location.get("street", "")

                # Apply location filters (case-insensitive exact match)
                if location_filters:
                    normalized_location = {k: (location.get(k, "") or "").strip().lower() for k in location_filters}
                    # If any filter does not match, skip this record entirely
                    if any(normalized_location.get(k, "") != v for k, v in location_filters.items()):
                        continue

                for q in payload.get("questions", []):
                    number = q.get("number")
                    answer = q.get("answer")
                    text = q.get("text") or ""
                    if isinstance(answer, list):
                        answer_str = "; ".join(str(a) for a in answer)
                    else:
                        answer_str = "" if answer is None else str(answer)
                    if isinstance(number, int):
                        # Store only the answer value; headers will contain the question text
                        answers_by_number[number] = answer_str
            except json.JSONDecodeError:
                # If description is not valid JSON, leave location/answers empty
                pass

            manager_name = getattr(getattr(record.collector, "manager", None), "full_name", "")

            row_base = [
                record.id,
                record.collector.full_name,
                record.collector.phone_number,
                manager_name,
                record.agent_name or "",
                record.agent_till_number or "",
                "" if record.latitude is None else str(record.latitude),
                "" if record.longitude is None else str(record.longitude),
                record.title,
                record.created_at.isoformat(),
                country,
                region,
                district,
                ward,
                street,
            ]

            row_answers = [answers_by_number.get(i, "") for i in range(1, 20)]
            writer.writerow(row_base + row_answers)

        return response


class ChangePasswordView(APIView):
    """Allow an authenticated user to change their own password."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password changed successfully"}, status=status.HTTP_200_OK)


class DataCollectorPasswordResetView(APIView):
    """Allow managers/super admins to reset a collector's password.

    Note: For security we do not expose existing passwords; managers can only
    set a new password for the collector.
    """

    permission_classes = [IsAuthenticated, IsManager | IsSuperAdmin]

    def post(self, request, pk, *args, **kwargs):
        user = request.user

        # Limit accessible collectors based on manager/super admin role.
        qs = User.objects.filter(role=User.Role.DATA_COLLECTOR)
        if user.role == User.Role.SUPER_ADMIN:
            pass
        elif user.role == User.Role.MANAGER:
            qs = qs.filter(manager=user)
        else:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            collector = qs.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "Collector not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = DataCollectorPasswordResetSerializer(
            data=request.data,
            context={"request": request, "collector": collector},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password reset successfully"}, status=status.HTTP_200_OK)
