import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase, override_settings
from django.utils import timezone, translation

from crudkit.models import ChangeLog, FeedItem, parse_ck_id
from crudkit_mcp.models import AccessToken, OAuthClient
from crudkit_mcp.server import PROTOCOL_VERSION, MCPServer
from crudkit_mcp.tools import Tool
from tests.testapp.models import Customer, Topic

EXTRA_TOOL = Tool("list_records", "Overridden", lambda user, arguments: "custom")


def grant(user, model, *actions):
    permissions = Permission.objects.filter(
        content_type__app_label=model._meta.app_label,
        codename__in=[f"{action}_{model._meta.model_name}" for action in actions],
    )
    user.user_permissions.add(*permissions)


class MCPTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="testpass")
        grant(self.user, Customer, "view")
        grant(self.user, Topic, "view")
        self.topic = Topic.objects.create(name="Billing", created_by=self.user, updated_by=self.user)
        self.customer = Customer.objects.create(
            name="Acme Corp", topic=self.topic, created_by=self.user, updated_by=self.user
        )

    def missing_id(self, model):
        """A CK-ID of the right type that no row has. Postgres keeps its
        sequences across tests, so pk values can't be assumed."""
        last = model.objects.order_by("-pk").first()
        return f"{model.TYPE_ID}{parse_ck_id(last.id)[1] + 1 if last else 1}"

    def server(self, scopes=("read",), user=None):
        # Fresh user so permission grants in the test aren't hidden by the perm cache.
        return MCPServer(User.objects.get(pk=(user or self.user).pk), oauth_scopes=list(scopes))

    def tool_names(self, **kwargs):
        result = self.server(**kwargs).handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        return [tool["name"] for tool in result["result"]["tools"]]

    def call(self, name, arguments=None, **kwargs):
        result = self.server(**kwargs).handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments or {}}}
        )["result"]
        text = result["content"][0]["text"]
        if result["isError"]:
            return {"error": text}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


class MCPServerProtocolTest(MCPTestCase):
    def test_initialize(self):
        result = self.server().handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(result["id"], 1)
        self.assertEqual(result["result"]["protocolVersion"], PROTOCOL_VERSION)
        self.assertEqual(result["result"]["serverInfo"]["name"], "crudkit")

    def test_initialize_echoes_supported_client_version(self):
        result = self.server().handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
        )
        self.assertEqual(result["result"]["protocolVersion"], "2025-06-18")

    @override_settings(CRUDKIT_MCP_SERVER_NAME="acme-crm")
    def test_server_name_setting(self):
        result = self.server().handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(result["result"]["serverInfo"]["name"], "acme-crm")

    def test_notifications_return_none(self):
        server = self.server()
        self.assertIsNone(server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIsNone(server.handle_message({"jsonrpc": "2.0", "method": "notifications/cancelled"}))

    def test_ping(self):
        result = self.server().handle_message({"jsonrpc": "2.0", "id": 7, "method": "ping"})
        self.assertEqual(result, {"jsonrpc": "2.0", "id": 7, "result": {}})

    def test_unknown_method(self):
        result = self.server().handle_message({"jsonrpc": "2.0", "id": 5, "method": "unknown/method", "params": {}})
        self.assertEqual(result["error"]["code"], -32601)

    def test_batch_request_rejected(self):
        result = self.server().handle_message([{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
        self.assertEqual(result["error"]["code"], -32600)
        self.assertIsNone(result["id"])

    def test_tools_call_without_read_scope(self):
        self.assertIn("scope", self.call("search", {"query": "acme"}, scopes=())["error"])

    def test_mcp_exclude(self):
        with patch.object(Customer.CrudKitSettings, "mcp_exclude", True, create=True):
            self.assertNotIn("CUS", [entry["type"] for entry in self.call("describe_types")])

    def test_tools_call_unknown_tool(self):
        self.assertIn("Unknown tool", self.call("nonexistent")["error"])


class ReadToolsTest(MCPTestCase):
    def test_tool_set_is_fixed(self):
        self.assertEqual(self.tool_names(), ["describe_types", "search", "list_records", "get_record"])

    def test_read_tools_are_annotated_read_only(self):
        result = self.server().handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        for tool in result["result"]["tools"]:
            self.assertTrue(tool["annotations"]["readOnlyHint"], tool["name"])

    def test_type_enum_follows_view_permission(self):
        result = self.server().handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        schema = next(t for t in result["result"]["tools"] if t["name"] == "list_records")["inputSchema"]
        self.assertEqual(set(schema["properties"]["type"]["enum"]), {"CUS", "TOP"})

    def test_describe_types_lists_visible_types(self):
        summaries = self.call("describe_types")
        self.assertEqual(
            summaries,
            [
                {"type": "TOP", "name": "topic", "name_plural": "topics"},
                {"type": "CUS", "name": "customer", "name_plural": "customers"},
            ],
        )

    def test_describe_type_details_fields_and_filters(self):
        data = self.call("describe_types", {"type": "CUS"})
        self.assertEqual(data["filters"]["status"]["enum"], ["active", "churned"])
        self.assertIn("created_at_from", data["filters"])
        self.assertNotIn("id", data["filters"])
        self.assertIn("name", data["fields"])
        self.assertNotIn("created_by", data["fields"])
        self.assertTrue(data["searchable"])
        self.assertFalse(data["can_update"])
        self.assertEqual(data["actions"], {})  # No change permission.

    def test_describe_unknown_type(self):
        self.assertIn("Unknown type", self.call("describe_types", {"type": "ZZZ"})["error"])
        # A real type the user may not view.
        self.assertIn("error", self.call("describe_types", {"type": "TIC"}))

    def test_search(self):
        self.assertEqual(
            self.call("search", {"query": "acme"}),
            [{"id": self.customer.id, "label": "Acme Corp", "object_images": []}],
        )
        self.assertEqual(self.call("search", {"query": ""}), "No query provided")
        self.assertEqual(self.call("search", {"query": "zzz"}), "No results found")

    def test_search_respects_permissions(self):
        other = User.objects.create_user("other")
        self.assertEqual(self.call("search", {"query": "acme"}, user=other), "No results found")

    def test_list_records(self):
        Customer.objects.create(name="Other", status="churned", created_by=self.user, updated_by=self.user)
        Customer.objects.create(name="Acme Gone", deleted=True, created_by=self.user, updated_by=self.user)

        def listed(**arguments):
            return self.call("list_records", {"type": "CUS", **arguments})

        self.assertEqual(listed()["total"], 2)
        self.assertEqual(listed(filters={"name": "acme"})["total"], 1)
        self.assertEqual(listed(filters={"status": "churned"})["results"][0]["name"], "Other")
        self.assertEqual(listed(filters={"topic": self.topic.id})["results"][0]["id"], self.customer.id)
        self.assertEqual(listed(query="other")["total"], 1)
        self.assertEqual(len(listed(limit=1)["results"]), 1)
        self.assertEqual(listed(order_by="-name")["results"][0]["name"], "Other")

    def test_list_records_rejects_bad_arguments(self):
        self.assertIn("Unknown type", self.call("list_records", {"type": "ZZZ"})["error"])
        self.assertIn("Unknown filter", self.call("list_records", {"type": "CUS", "filters": {"nope": 1}})["error"])
        self.assertIn("Cannot order by", self.call("list_records", {"type": "CUS", "order_by": "password"})["error"])

    def test_list_records_needs_view_permission(self):
        self.assertIn("error", self.call("list_records", {"type": "TIC"}))

    def test_get_record(self):
        FeedItem.objects.create(
            parent_object=self.customer, body="Called them", created_by=self.user, updated_by=self.user
        )
        data = self.call("get_record", {"id": self.customer.id})
        self.assertEqual(data["name"], "Acme Corp")
        self.assertEqual(data["topic"]["name"], "Billing")
        self.assertEqual(data["feed"][0]["body"], "Called them")
        self.assertEqual(data["actions"], [])  # No change permission.

    def test_get_record_errors(self):
        self.assertIn("not found", self.call("get_record", {"id": self.missing_id(Customer)})["error"])
        self.assertIn("Invalid ID", self.call("get_record", {"id": "1"})["error"])
        self.assertIn("Unknown type", self.call("get_record", {"id": "ZZZ1"})["error"])

    @override_settings(CRUDKIT_MCP_EXTRA_TOOLS=["crudkit_mcp.tests.test_mcp.EXTRA_TOOL"])
    def test_extra_tools_override_generated(self):
        self.assertEqual(self.call("list_records"), "custom")


class WriteToolsTest(MCPTestCase):
    WRITE = ("read", "write")

    def setUp(self):
        super().setUp()
        grant(self.user, Customer, "add", "change")

    def test_write_tools_need_setting(self):
        self.assertNotIn("update_record", self.tool_names(scopes=self.WRITE))

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_write_tools_need_write_scope(self):
        self.assertNotIn("update_record", self.tool_names())
        self.assertEqual(
            self.tool_names(scopes=self.WRITE)[4:],
            ["create_record", "update_record", "run_action", "add_note"],
        )

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_describe_types_reports_write_permissions(self):
        data = self.call("describe_types", {"type": "CUS"}, scopes=self.WRITE)
        self.assertTrue(data["can_create"])
        self.assertTrue(data["can_update"])
        self.assertEqual(data["actions"], {"mark_churned": "Mark churned"})
        self.assertEqual(data["required_on_create"], ["name"])

        topic = self.call("describe_types", {"type": "TOP"}, scopes=self.WRITE)
        self.assertFalse(topic["can_create"])
        self.assertFalse(topic["can_update"])

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_create(self):
        data = self.call(
            "create_record", {"type": "CUS", "fields": {"name": "New Co", "topic": self.topic.id}}, scopes=self.WRITE
        )
        customer = Customer.objects.get(pk=data["id"])
        self.assertEqual(customer.name, "New Co")
        self.assertEqual(customer.topic, self.topic)
        self.assertEqual(customer.created_by, self.user)
        self.assertTrue(ChangeLog.objects.filter(related_object_id=customer.pk).exists())

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_create_needs_add_permission(self):
        result = self.call("create_record", {"type": "TOP", "fields": {"name": "x"}}, scopes=self.WRITE)
        self.assertEqual(result["error"], "Permission denied")

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_update_writes_changelog(self):
        data = self.call(
            "update_record", {"id": self.customer.id, "fields": {"name": "Acme Inc"}}, scopes=self.WRITE
        )
        self.assertEqual(data["name"], "Acme Inc")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Acme Inc")
        change = ChangeLog.objects.get(related_object_id=self.customer.pk)
        self.assertEqual(change.field_changes["name"], ["Acme Corp", "Acme Inc"])

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_update_rejects_unknown_and_read_only_fields(self):
        for fields in ({"nope": 1}, {"created_by": 1}, {}):
            result = self.call("update_record", {"id": self.customer.id, "fields": fields}, scopes=self.WRITE)
            self.assertIn("error", result, fields)

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_update_rejects_missing_fk_instead_of_clearing_it(self):
        missing = self.missing_id(Topic)
        result = self.call("update_record", {"id": self.customer.id, "fields": {"topic": missing}}, scopes=self.WRITE)
        self.assertIn("not found", result["error"])
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.topic, self.topic)

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_update_needs_change_permission(self):
        other = User.objects.create_user("other")
        grant(other, Customer, "view")
        result = self.call(
            "update_record", {"id": self.customer.id, "fields": {"name": "x"}}, scopes=self.WRITE, user=other
        )
        self.assertIn("not found, or not available for change", result["error"])
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Acme Corp")

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_run_action(self):
        result = self.call("run_action", {"id": self.customer.id, "action": "mark_churned"}, scopes=self.WRITE)
        self.assertEqual(result, {"kind": "object", "id": self.customer.id})
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, "churned")

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_run_unknown_action(self):
        result = self.call("run_action", {"id": self.customer.id, "action": "delete_everything"}, scopes=self.WRITE)
        self.assertIn("not available", result["error"])

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_add_note(self):
        self.call("add_note", {"id": self.customer.id, "body": "Renewal due"}, scopes=self.WRITE)
        self.assertEqual(FeedItem.objects.get().body, "Renewal due")

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_add_note_needs_change_permission(self):
        result = self.call("add_note", {"id": self.topic.id, "body": "x"}, scopes=self.WRITE)
        self.assertIn("not available for change", result["error"])
        self.assertFalse(FeedItem.objects.exists())

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_add_note_rejects_unexposed_types(self):
        result = self.call("add_note", {"id": "VIW1", "body": "x"}, scopes=self.WRITE)
        self.assertIn("Unknown type", result["error"])


class McpViewIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="testpass")
        grant(self.user, Customer, "view")
        self.oauth_client = OAuthClient.objects.create(
            client_name="Test App",
            redirect_uris=["http://localhost:3000/callback"],
        )
        self.token = AccessToken.objects.create(
            client=self.oauth_client,
            user=self.user,
            scopes="read",
            expires_at=timezone.now() + timedelta(hours=1),
        )

    def _mcp_request(self, method, params=None):
        return self.client.post(
            "/api/v1/mcp/",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )

    def test_initialize_via_http(self):
        response = self._mcp_request("initialize")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["protocolVersion"], PROTOCOL_VERSION)
        self.assertEqual(response["Mcp-Protocol-Version"], PROTOCOL_VERSION)

    def test_notifications_initialized_returns_202(self):
        response = self.client.post(
            "/api/v1/mcp/",
            data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 202)

    def test_tools_call_via_http(self):
        response = self._mcp_request("tools/call", {"name": "list_records", "arguments": {"type": "CUS"}})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["result"]["isError"])

    def test_tools_list_uses_token_user(self):
        tools = self._mcp_request("tools/list").json()["result"]["tools"]
        types = next(t for t in tools if t["name"] == "list_records")["inputSchema"]["properties"]["type"]["enum"]
        self.assertEqual(types, ["CUS"])

    def test_invalid_json(self):
        response = self.client.post(
            "/api/v1/mcp/",
            data="not json",
            content_type="text/plain",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 415)

    def test_batch_request_via_http(self):
        response = self.client.post(
            "/api/v1/mcp/",
            data=json.dumps([{"jsonrpc": "2.0", "id": 1, "method": "ping"}]),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"]["code"], -32600)

    def test_get_returns_event_stream(self):
        response = self.client.get("/api/v1/mcp/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response["Content-Type"])
        self.assertEqual(response["Cache-Control"], "no-cache")

    def test_post_without_auth_returns_401_with_www_authenticate(self):
        response = self.client.post(
            "/api/v1/mcp/",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response["WWW-Authenticate"],
            'Bearer resource_metadata="http://testserver/.well-known/oauth-protected-resource"',
        )

    def test_post_without_trailing_slash_does_not_redirect(self):
        # claude.ai strips the trailing slash from MCP URLs and does not
        # follow 301/308 redirects on POST — the endpoint must answer on
        # both /api/v1/mcp and /api/v1/mcp/.
        response = self.client.post(
            "/api/v1/mcp",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)


class ExposedModelsTest(MCPTestCase):
    def types(self, **kwargs):
        return [entry["type"] for entry in self.call("describe_types", **kwargs)]

    def test_django_models_are_not_exposed(self):
        # crudkit gives User a TYPE_ID so it can be addressed by CK-ID.
        self.user.is_superuser = True
        self.user.save()
        types = self.types()
        self.assertNotIn("USR", types)
        self.assertIn("CUS", types)

    @override_settings(CRUDKIT_MCP_MODELS=["CUS"])
    def test_allowlist(self):
        self.assertEqual(self.types(), ["CUS"])

    def test_type_names_do_not_follow_the_active_language(self):
        with translation.override("da"):
            self.assertEqual(self.call("describe_types", {"type": "CUS"})["name"], "customer")
