from django.urls import path

from .views import (
    ChangePasswordView,
    DataCollectionRecordDetailView,
    DataCollectionRecordExportView,
    DataCollectionRecordListCreateView,
    DataCollectionRecordManagerListView,
    DataCollectorDetailView,
    DataCollectorListCreateView,
    DataCollectorPasswordResetView,
    DataCollectorStatusUpdateView,
    LoginView,
    LogoutView,
    MeView,
    ManagerDetailView,
    ManagerListCreateView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("managers/create/", ManagerListCreateView.as_view(), name="manager-create"),
    path("managers/", ManagerListCreateView.as_view(), name="manager-list"),
    path("managers/<int:pk>/", ManagerDetailView.as_view(), name="manager-detail"),
    path("data-collectors/create/", DataCollectorListCreateView.as_view(), name="data-collector-create"),
    path("data-collectors/", DataCollectorListCreateView.as_view(), name="data-collector-list"),
    path("data-collectors/<int:pk>/", DataCollectorDetailView.as_view(), name="data-collector-detail"),
    path(
        "data-collectors/<int:pk>/status/",
        DataCollectorStatusUpdateView.as_view(),
        name="data-collector-status",
    ),
    path(
        "data-collectors/<int:pk>/reset-password/",
        DataCollectorPasswordResetView.as_view(),
        name="data-collector-reset-password",
    ),
    path("data-collection-records/", DataCollectionRecordListCreateView.as_view(), name="data-collection-records"),
    path(
        "data-collection-records/manager/",
        DataCollectionRecordManagerListView.as_view(),
        name="data-collection-records-manager",
    ),
    path(
        "data-collection-records/<int:pk>/",
        DataCollectionRecordDetailView.as_view(),
        name="data-collection-record-detail",
    ),
    path(
        "data-collection-records/export/",
        DataCollectionRecordExportView.as_view(),
        name="data-collection-records-export",
    ),
]
