"""
Change hints pushed to connected browsers over `crudkit_api.consumers.ChangesConsumer`.

A hint only says "TYPE_ID/pk was saved or deleted by user X"; clients refetch
through the permission-checked REST API. Sending is a no-op unless channels is
installed and a channel layer is configured.
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


def broadcast_change(type_id: str, pk, action: str, by=None):
    layer = get_channel_layer() if get_channel_layer else None
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            group_name(type_id),
            {"type": "crudkit.change", "model": type_id, "id": pk, "action": action, "by": by},
        )
    except Exception:
        # A missing/broken channel layer must not fail the save that just
        # committed; clients fall back to polling when their socket is down.
        logger.exception("Failed to broadcast %s %s pk=%s", action, type_id, pk)
