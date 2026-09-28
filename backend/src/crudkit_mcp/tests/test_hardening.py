"""MCP writes: undoing approval-gated changes needs approval, and the write
rate limit neither breaks on nor silently depends on the cache backend."""

from unittest.mock import patch

from django.core import checks
from django.test import override_settings

from crudkit.models import ChangeLog
from crudkit_assistant.models import AssistantProposal
from crudkit_mcp.checks import check_write_rate
from crudkit_mcp.tests.test_mcp import MCPTestCase, grant
from tests.testapp.models import Customer

WRITE = ("read", "write")


@override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
class UndoApprovalTest(MCPTestCase):
    def setUp(self):
        super().setUp()
        grant(self.user, Customer, "change")

    def test_undoing_an_approval_field_change_is_proposed(self):
        with patch.object(Customer.CrudKitSettings, "approval_fields", ["status"], create=True):
            # A person changed the approval field; an MCP client tries to undo it.
            change_set = self.call(
                "update_record", {"id": self.customer.id, "fields": {"name": "Renamed"}}, scopes=WRITE
            )["change_set"]
            ChangeLog.objects.filter(change_set=change_set).update(
                field_changes={"status": ["active", "churned"], "name": ["Acme Corp", "Renamed"]}
            )
            result = self.call("undo", {"change_set": change_set}, scopes=WRITE)
        self.assertEqual(result["status"], "pending_approval")
        proposal = AssistantProposal.objects.get()
        self.assertEqual((proposal.kind, proposal.source), ("revert", "mcp"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Renamed")

    @override_settings(
        CRUDKIT_MCP_WRITE_RATE="1/min", CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_a_cache_that_stores_nothing_does_not_block_writes(self):
        for name in ("B", "C"):
            result = self.call("update_record", {"id": self.customer.id, "fields": {"name": name}}, scopes=WRITE)
            self.assertNotIn("error", result)


class WriteRateCheckTest(MCPTestCase):
    @override_settings(CRUDKIT_MCP_WRITE_RATE="10/fortnight")
    def test_invalid_rate_is_a_startup_error(self):
        self.assertEqual([e.id for e in check_write_rate(None)], ["crudkit_mcp.E001"])

    @override_settings(
        CRUDKIT_MCP_WRITE_RATE="60/min",
        CRUDKIT_MCP_WRITE_ENABLED=True,
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    )
    def test_per_process_cache_warns_when_writes_are_enabled(self):
        (warning,) = check_write_rate(None)
        self.assertEqual((warning.id, warning.level), ("crudkit_mcp.W001", checks.WARNING))
        with override_settings(CRUDKIT_MCP_WRITE_ENABLED=False):
            self.assertEqual(check_write_rate(None), [])

    @override_settings(CRUDKIT_MCP_WRITE_RATE=None)
    def test_no_limit_no_warning(self):
        self.assertEqual(check_write_rate(None), [])


@override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
class ChangeLogPermissionTest(MCPTestCase):
    def test_get_record_leaves_out_the_change_log_without_permission(self):
        self.assertNotIn("changelog", self.call("get_record", {"id": self.customer.id}))
        grant(self.user, ChangeLog, "view")
        self.assertIn("changelog", self.call("get_record", {"id": self.customer.id}))
