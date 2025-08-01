"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from rooms.middleware import JWTAuthMiddleware
from channels.security.websocket import AllowedHostsOriginValidator
from rooms.routing import websocket_urlpatterns as room_websocket_urlpatterns
from users.routing import websocket_urlpatterns as user_websocket_urlpatterns

websocket_urlpatterns = room_websocket_urlpatterns + user_websocket_urlpatterns


application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
            URLRouter(
                websocket_urlpatterns
            )
        ),
})