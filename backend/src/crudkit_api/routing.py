from channels.auth import AuthMiddlewareStack
from django.urls import re_path

from crudkit_api import consumers

websocket_urlpatterns = [
    re_path(r"ws/changes/$", AuthMiddlewareStack(consumers.ChangesConsumer.as_asgi())),
]
