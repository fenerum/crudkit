"""Mount under the API prefix, e.g. `path("api/v1/", include("crudkit_mcp.urls"))`.
The OAuth discovery documents must live at the site root: also include
`crudkit_mcp.well_known_urls` at "".
"""

from django.urls import path

from crudkit_mcp.oauth import AuthorizeView, OAuthRegisterView, TokenView
from crudkit_mcp.views import McpView

urlpatterns = [
    path("oauth/authorize/", AuthorizeView.as_view(), name="crudkit_mcp_oauth_authorize"),
    path("oauth/token/", TokenView.as_view(), name="crudkit_mcp_oauth_token"),
    path("oauth/register/", OAuthRegisterView.as_view(), name="crudkit_mcp_oauth_register"),
    # Clients disagree on the trailing slash; a redirect would drop the POST body.
    path("mcp", McpView.as_view(), name="crudkit_mcp_noslash"),
    path("mcp/", McpView.as_view(), name="crudkit_mcp"),
]
