"""
WebSocket that pushes change hints (see `crudkit.realtime`) to the SPA.

Outbound:
- {"type": "ready"}
- {"type": "change", "model": "<TYPE_ID>", "id": <pk>, "action": "saved"|"deleted", "by": <user_id>}

A saved hint only reaches users who may view that row. A deleted row can't be
checked any more, so its hint goes to every viewer of the model without
`id`/`by`.

Without a channel layer nothing would ever be pushed, so the socket closes with
4503 and the client keeps polling.
"""

from asgiref.sync import sync_to_async

from crudkit.authorization import has_model_permission, has_object_permission
from crudkit.models import BaseCrudKitModel
from crudkit.realtime import group_name
from crudkit.utils import get_model_types
from crudkit_api.ws_auth import AuthenticatedConsumer


def _viewable_type_ids(user) -> list[str]:
    return [type_id for type_id, model in get_model_types().items() if has_model_permission(user, model, "view")]


def _has_row_rules(model) -> bool:
    rules = getattr(getattr(model, "CrudKitSettings", None), "get_authorized_queryset", None)
    return rules is not None and rules is not BaseCrudKitModel.CrudKitSettings.get_authorized_queryset


class ChangesConsumer(AuthenticatedConsumer):
    async def connect(self):
        self.groups_joined: list[str] = []
        await super().connect()

    async def on_authenticated(self, user) -> bool:
        if self.channel_layer is None:
            await self.close(code=4503)
            return False
        self.user = user
        self.groups_joined = [group_name(t) for t in await sync_to_async(_viewable_type_ids)(user)]
        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.send_json({"type": "ready"})
        return True

    async def disconnect(self, close_code):
        await super().disconnect(close_code)
        for group in self.groups_joined:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def crudkit_change(self, event):
        pk, by = event["id"], event["by"]
        if event["action"] == "deleted":
            pk = by = None
        elif not await self._can_view_row(event["model"], pk):
            return
        await self.send_json({"type": "change", "model": event["model"], "id": pk, "action": event["action"], "by": by})

    async def _can_view_row(self, type_id: str, pk) -> bool:
        model = get_model_types().get(type_id)
        if model is None:
            return False
        # Joining the group already required model-level view permission, so
        # only row-level rules need a query (one per socket per saved row).
        if self.user.is_superuser or not _has_row_rules(model):
            return True
        return await sync_to_async(has_object_permission)(self.user, model(pk=pk))
