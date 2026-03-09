import csv
import json

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, DataCollectionRecord
from .permissions import IsSuperAdmin, IsManager, IsDataCollector
from .serializers import (
    ChangePasswordSerializer,
    DataCollectionRecordSerializer,
    DataCollectorCreateSerializer,
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

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"agent_surveys_{timestamp}.csv"

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)

        # Define CSV header
        question_headers = [f"Q{i}" for i in range(1, 20)]
        header = [
            "Record ID",
            "Collector Name",
            "Collector Phone",
            "Manager Name",
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

                for q in payload.get("questions", []):
                    number = q.get("number")
                    answer = q.get("answer")
                    if isinstance(answer, list):
                        answer_str = "; ".join(str(a) for a in answer)
                    else:
                        answer_str = "" if answer is None else str(answer)
                    if isinstance(number, int):
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
