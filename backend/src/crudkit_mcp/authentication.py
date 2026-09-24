from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from crudkit_mcp.models import AccessToken


class OAuthBearerAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None

        token_string = auth_header[len(self.keyword) + 1 :]

        try:
            token = AccessToken.objects.select_related("user", "client").get(token=token_string)
        except AccessToken.DoesNotExist:
            raise AuthenticationFailed("Invalid access token") from None

        if token.is_expired:
            raise AuthenticationFailed("Access token has expired")

        if not token.user.is_active:
            raise AuthenticationFailed("User is inactive")

        if not token.client.is_active:
            raise AuthenticationFailed("OAuth client is inactive")

        request.oauth_scopes = token.scopes.split()
        return (token.user, token)

    def authenticate_header(self, request):
        return self.keyword
