"""
Shared authentication for CrudKit WebSocket consumers.

Session-authenticated sockets (e.g. SAML) are ready as soon as they connect.
Browsers can't attach Authorization headers to a WebSocket upgrade, so JWT
clients send `{"type":"auth","token":...}` as the first frame instead.
"""

import asyncio
import json
from typing import Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken

# Sockets that don't authenticate within this many seconds get closed.
AUTH_TIMEOUT_SECONDS = 5


class AuthenticatedConsumer(AsyncWebsocketConsumer):
    """Subclasses implement `on_authenticated(user)` and `on_message(data)`.
    `self.user_id` is set before `on_authenticated` runs and cleared again if
    it rejects the user."""

    user_id: Optional[int] = None
    _auth_timeout_task: Optional[asyncio.Task] = None

    async def connect(self):
        self.user_id = None
        self._auth_timeout_task = None
        user = self.scope.get("user")
        await self.accept()
        if user and getattr(user, "is_authenticated", False):
            await self._finish_auth(user.pk)
            return
        self._auth_timeout_task = asyncio.create_task(self._auth_timeout())

    async def disconnect(self, close_code):
        self._cancel_auth_timeout()

    async def receive(self, text_data: Optional[str] = None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json({"type": "error", "message": "Invalid JSON"})
            return

        if self.user_id is not None:
            await self.on_message(data)
            return
        if data.get("type") != "auth":
            await self.send_json({"type": "error", "message": "Auth required."})
            await self.close(code=4001)
            return
        await self._handle_auth(data.get("token"))

    async def on_authenticated(self, user) -> bool:
        """Return False (after closing) to reject an authenticated user."""
        return True

    async def on_message(self, data: dict):
        pass

    async def send_json(self, payload: dict):
        await self.send(text_data=json.dumps(payload, default=str))

    def _cancel_auth_timeout(self):
        if self._auth_timeout_task is not None:
            self._auth_timeout_task.cancel()
            self._auth_timeout_task = None

    async def _auth_timeout(self):
        try:
            await asyncio.sleep(AUTH_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            return
        if self.user_id is None:
            await self.send_json({"type": "error", "message": "Auth timeout."})
            await self.close(code=4001)

    async def _handle_auth(self, token):
        if not token or not isinstance(token, str):
            await self.send_json({"type": "error", "message": "Missing token."})
            await self.close(code=4001)
            return
        try:
            user_id = AccessToken(token)[api_settings.USER_ID_CLAIM]
        except (TokenError, KeyError):
            await self.send_json({"type": "error", "message": "Invalid token."})
            await self.close(code=4001)
            return
        await self._finish_auth(user_id)

    async def _finish_auth(self, user_id):
        user = await self._get_user_by_id(user_id)
        if user is None or not user.is_active:
            await self.send_json({"type": "error", "message": "Invalid token."})
            await self.close(code=4001)
            return
        self._cancel_auth_timeout()
        self.user_id = user.pk
        if not await self.on_authenticated(user):
            self.user_id = None

    @database_sync_to_async
    def _get_user_by_id(self, user_id):
        try:
            return get_user_model().objects.get(pk=user_id)
        except get_user_model().DoesNotExist:
            return None
