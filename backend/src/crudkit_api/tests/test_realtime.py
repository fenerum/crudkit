import json
from unittest import mock

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.db import transaction
from django.test import TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken

from crudkit.realtime import broadcast_change
from crudkit_api.consumers import ChangesConsumer
from crudkit_api.tests.test_authorization import grant
from tests.testapp.models import Customer, Topic

IN_MEMORY_LAYER = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


def _create_customer(user, name="Acme"):
    return Customer.objects.create(name=name, created_by=user, updated_by=user)


def _create_customer_and_roll_back(user):
    with transaction.atomic():
        _create_customer(user)
        transaction.set_rollback(True)


# TransactionTestCase: the consumer reads the DB from another thread and
# on_commit callbacks must actually fire.
@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYER)
class ChangesConsumerTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="viewer", password="pw")
        grant(self.user, Customer, "view")

    async def _connect(self, user=None):
        communicator = WebsocketCommunicator(ChangesConsumer.as_asgi(), "/ws/changes/")
        if user is not None:
            communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        return communicator

    async def _receive(self, communicator):
        return json.loads(await communicator.receive_from())

    async def test_session_user_gets_change_hints_after_commit(self):
        communicator = await self._connect(self.user)
        self.assertEqual(await self._receive(communicator), {"type": "ready"})

        customer = await sync_to_async(_create_customer)(self.user)
        self.assertEqual(
            await self._receive(communicator),
            {"type": "change", "model": "CUS", "id": customer.pk, "action": "saved", "by": self.user.pk},
        )

        await sync_to_async(customer.delete)()
        self.assertEqual(
            await self._receive(communicator),
            {"type": "change", "model": "CUS", "id": None, "action": "deleted", "by": None},
        )
        await communicator.disconnect()

    async def test_jwt_auth_frame(self):
        communicator = await self._connect()
        await communicator.send_to(json.dumps({"type": "auth", "token": str(AccessToken.for_user(self.user))}))
        self.assertEqual(await self._receive(communicator), {"type": "ready"})
        await communicator.disconnect()

    async def test_invalid_token_closes_4001(self):
        communicator = await self._connect()
        await communicator.send_to(json.dumps({"type": "auth", "token": "nope"}))
        self.assertEqual((await self._receive(communicator))["type"], "error")
        self.assertEqual((await communicator.receive_output())["code"], 4001)

    async def test_no_hints_for_models_without_view_permission(self):
        communicator = await self._connect(self.user)
        await self._receive(communicator)
        await sync_to_async(Topic.objects.create)(name="t", created_by=self.user, updated_by=self.user)
        self.assertTrue(await communicator.receive_nothing())
        await communicator.disconnect()

    async def test_no_saved_hint_for_rows_outside_the_users_scope(self):
        def only_acme(user, queryset, action):
            return queryset.filter(name="Acme")

        with mock.patch.object(Customer.CrudKitSettings, "get_authorized_queryset", only_acme, create=True):
            communicator = await self._connect(self.user)
            await self._receive(communicator)
            await sync_to_async(_create_customer)(self.user, name="Hidden")
            acme = await sync_to_async(_create_customer)(self.user)
            self.assertEqual((await self._receive(communicator))["id"], acme.pk)
            self.assertTrue(await communicator.receive_nothing())
            await communicator.disconnect()

    async def test_no_row_query_without_row_level_rules(self):
        communicator = await self._connect(self.user)
        await self._receive(communicator)
        with mock.patch("crudkit_api.consumers.has_object_permission") as has_object_permission:
            await sync_to_async(_create_customer)(self.user)
            self.assertEqual((await self._receive(communicator))["action"], "saved")
        has_object_permission.assert_not_called()
        await communicator.disconnect()

    async def test_no_hint_when_transaction_rolls_back(self):
        communicator = await self._connect(self.user)
        await self._receive(communicator)
        await sync_to_async(_create_customer_and_roll_back)(self.user)
        self.assertTrue(await communicator.receive_nothing())
        await communicator.disconnect()

    @override_settings(CHANNEL_LAYERS={})
    async def test_closes_4503_without_channel_layer(self):
        communicator = await self._connect(self.user)
        self.assertEqual((await communicator.receive_output())["code"], 4503)


class BroadcastWithoutLayerTests(TransactionTestCase):
    def test_broadcast_is_a_noop_without_channel_layer(self):
        broadcast_change("CUS", 1, "saved")
