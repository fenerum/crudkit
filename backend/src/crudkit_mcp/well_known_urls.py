"""OAuth discovery (RFC 8414 / RFC 9728). Include at the site root:
`path("", include("crudkit_mcp.well_known_urls"))`. Newer MCP clients append
the resource path, e.g. /.well-known/oauth-protected-resource/api/v1/mcp.
"""

from django.urls import re_path

from crudkit_mcp.oauth import oauth_authorization_server_metadata, oauth_protected_resource_metadata

urlpatterns = [
    re_path(
        r"^\.well-known/oauth-authorization-server(?P<suffix>/.*)?$",
        oauth_authorization_server_metadata,
        name="crudkit_mcp_authorization_server",
    ),
    re_path(
        r"^\.well-known/oauth-protected-resource(?P<suffix>/.*)?$",
        oauth_protected_resource_metadata,
        name="crudkit_mcp_protected_resource",
    ),
]
