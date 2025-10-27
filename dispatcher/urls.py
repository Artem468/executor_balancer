from django.urls import path

from dispatcher.views import DispatcherView, DailySummaryView

urlpatterns = [
    path('', DispatcherView.as_view(), name='dispatch'),
    path('summary/', DailySummaryView.as_view(), name='summary'),
]
