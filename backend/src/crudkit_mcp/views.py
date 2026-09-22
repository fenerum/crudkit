from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView

from crudkit_mcp.authentication import OAuthBearerAuthentication
from crudkit_mcp.conf import absolute_url
from crudkit_mcp.server import PROTOCOL_VERSION, MCPServer


class McpView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        response = StreamingHttpResponse(
            streaming_content=iter([]),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["Mcp-Protocol-Version"] = PROTOCOL_VERSION
        return response

    def post(self, request):
        authenticator = OAuthBearerAuthentication()
        try:
            auth_result = authenticator.authenticate(request)
        except AuthenticationFailed:
            auth_result = None

        if auth_result is None:
            resource_metadata_url = absolute_url(request, "crudkit_mcp_protected_resource")
            response = JsonResponse({"error": "unauthorized"}, status=401)
            response["WWW-Authenticate"] = f'Bearer resource_metadata="{resource_metadata_url}"'
            return response

        user, token = auth_result
        server = MCPServer(user, oauth_scopes=getattr(request, "oauth_scopes", []))
        result = server.handle_message(request.data)

        if result is None:
            response = JsonResponse({}, status=202)
        else:
            response = JsonResponse(result)

        response["Mcp-Protocol-Version"] = PROTOCOL_VERSION
        return response
