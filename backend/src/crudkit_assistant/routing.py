from channels.auth import AuthMiddlewareStack
from django.urls import re_path

from crudkit_assistant import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/assistant/(?P<type_id>[A-Z]{3})/(?P<pk>\d+)/$",
        AuthMiddlewareStack(consumers.AssistantConsumer.as_asgi()),
    ),
]
