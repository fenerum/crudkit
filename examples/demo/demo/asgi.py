import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo.settings")
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402 — needs the app registry loaded above

from crudkit_api.routing import websocket_urlpatterns as changes_urlpatterns  # noqa: E402
from crudkit_assistant.routing import websocket_urlpatterns as assistant_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(changes_urlpatterns + assistant_urlpatterns),
    }
)
