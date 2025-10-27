from django.urls import path

from dispatcher.views import DispatcherView

urlpatterns = [
    path('', DispatcherView.as_view(), name='dispatch'),
]
