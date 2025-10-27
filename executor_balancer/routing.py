from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/newRequest/$', consumers.NewRequestConsumer.as_asgi()),
    re_path(r'ws/dispatched/$', consumers.DispatchRequestsConsumer.as_asgi()),
]
