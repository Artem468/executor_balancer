"""
URL configuration for executor_balancer project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from core.views import UserViewSet, RequestViewSet, KeyDataTypesViewSet
from dispatcher.views import ExportDispatchSummaryExcelView

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'requests', RequestViewSet, basename='request')
router.register(r'dataTypes', KeyDataTypesViewSet, basename='dataTypes')

urlpatterns = [
    path('core/', include('core.urls')),
    path('api/dispatch/', include('dispatcher.urls')),
    path('api/', include(router.urls)),
    path('export/logs', ExportDispatchSummaryExcelView.as_view(), name='export-logs'),
    path(
        "schema/",
        SpectacularAPIView.as_view(),
        name="schema",
    ),
    path(
        "swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
