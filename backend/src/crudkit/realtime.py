"""
Change hints pushed to connected browsers over `crudkit_api.consumers.ChangesConsumer`.

A hint only says "TYPE_ID/pk was saved or deleted by user X"; clients refetch
through the permission-checked REST API. Messages for one user (their task
progress) go to that user's own group with the payload. Sending is a no-op
unless channels is installed and a channel layer is configured.
"""

import logging

from asgiref.sync import async_to_sync

try:
    from channels.layers import get_channel_layer
except ImportError:  # channels is only installed with the `realtime` extra
    get_channel_layer = None

logger = logging.getLogger(__name__)


def group_name(type_id: str) -> str:
    return f"crudkit.changes.{type_id}"


def user_group(user_id) -> str:
    return f"crudkit.user.{user_id}"


def _send(group: str, message: dict) -> None:
    layer = get_channel_layer() if get_channel_layer else None
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(group, message)
    except Exception:
        # A missing/broken channel layer must not fail the write that just
        # happened; clients fall back to polling when their socket is down.
        logger.exception("Failed to send %s to %s", message.get("type"), group)


def broadcast_change(type_id: str, pk, action: str, by=None):
    _send(group_name(type_id), {"type": "crudkit.change", "model": type_id, "id": pk, "action": action, "by": by})


def send_to_user(user_id, message: dict):
    _send(user_group(user_id), message)
