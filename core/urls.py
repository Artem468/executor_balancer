from django.urls import path
from .views import HealthCheckView, RequestStatsAPIView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("stats/", RequestStatsAPIView.as_view(), name="stats"),
]
