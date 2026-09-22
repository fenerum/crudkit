import json
import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError

from crudkit_mcp.tools import get_tools

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-03-26"
SUPPORTED_PROTOCOL_VERSIONS = {"2025-03-26", "2025-06-18"}
SERVER_VERSION = "1.0.0"


def get_server_name() -> str:
    return getattr(settings, "CRUDKIT_MCP_SERVER_NAME", "crudkit")


class MCPServer:
    def __init__(self, user, oauth_scopes: list[str] | None = None):
        self.user = user
        self.oauth_scopes = oauth_scopes or []

    def handle_message(self, message: dict) -> dict | None:
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}

        handler = {
            "initialize": self._handle_initialize,
            "notifications/initialized": self._handle_initialized,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
        }.get(method)

        if handler is None:
            if msg_id is None:
                return None  # Unknown notifications need no reply.
            return self._error_response(msg_id, -32601, f"Method not found: {method}")

        try:
            result = handler(params)
            if result is None:
                return None
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as e:
            logger.exception("MCP error handling %s", method)
            return self._error_response(msg_id, -32603, str(e))

    def _handle_initialize(self, params: dict) -> dict:
        requested = params.get("protocolVersion")
        return {
            "protocolVersion": requested if requested in SUPPORTED_PROTOCOL_VERSIONS else PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": get_server_name(), "version": SERVER_VERSION},
        }

    def _handle_initialized(self, params: dict) -> None:
        return None

    def _handle_ping(self, params: dict) -> dict:
        return {}

    def _handle_tools_list(self, params: dict) -> dict:
        return {"tools": [tool.definition() for tool in get_tools(self.user, self.oauth_scopes).values()]}

    def _handle_tools_call(self, params: dict) -> dict:
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}

        if "read" not in self.oauth_scopes:
            return _error_content("Insufficient scope: 'read' required")

        tool = get_tools(self.user, self.oauth_scopes).get(tool_name)
        if tool is None:
            return _error_content(f"Unknown tool: {tool_name}")

        try:
            result = tool.handler(self.user, arguments)
        except PermissionDenied:
            return _error_content("Permission denied")
        except (KeyError, ValueError, TypeError, ValidationError) as e:
            return _error_content(f"Error: {e}")
        except Exception as e:
            logger.exception("Tool error: %s", tool_name)
            return _error_content(f"Error: {e}")
        text = result if isinstance(result, str) else json.dumps(result, default=str)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    def _error_response(self, msg_id, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _error_content(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": True}
