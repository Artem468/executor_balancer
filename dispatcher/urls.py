from django.urls import path

from dispatcher.views import DailySummaryView

urlpatterns = [
    path('summary/', DailySummaryView.as_view(), name='summary'),
]
