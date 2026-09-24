import calendar
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect as http_redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from crudkit_mcp.conf import absolute_url, base_url, supported_scopes
from crudkit_mcp.models import AccessToken, AuthorizationCode, OAuthClient, RefreshToken

AUTH_CODE_LIFETIME = timedelta(minutes=10)
ACCESS_TOKEN_LIFETIME = timedelta(hours=1)
REFRESH_TOKEN_LIFETIME = timedelta(days=90)


def _build_redirect_url(base_uri: str, **params) -> str:
    separator = "&" if "?" in base_uri else "?"
    return f"{base_uri}{separator}{urlencode(params)}"


def oauth_authorization_server_metadata(request, suffix=None):
    return JsonResponse(
        {
            "issuer": base_url(request),
            "authorization_endpoint": absolute_url(request, "crudkit_mcp_oauth_authorize"),
            "token_endpoint": absolute_url(request, "crudkit_mcp_oauth_token"),
            "registration_endpoint": absolute_url(request, "crudkit_mcp_oauth_register"),
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": supported_scopes(),
        }
    )


def oauth_protected_resource_metadata(request, suffix=None):
    return JsonResponse(
        {
            "resource": absolute_url(request, "crudkit_mcp"),
            "authorization_servers": [base_url(request)],
            "scopes_supported": supported_scopes(),
            "bearer_methods_supported": ["header"],
        }
    )


class AuthorizeView(LoginRequiredMixin, View):
    def get(self, request):
        redirect_uri = request.GET.get("redirect_uri")
        code_challenge = request.GET.get("code_challenge")
        state = request.GET.get("state", "")

        client, scope, error = self._validate_params(request)
        if error:
            return JsonResponse({"error": error}, status=400)

        return render(
            request,
            "crudkit_mcp/authorize.html",
            {
                "client": client,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "state": state,
                "scope": scope,
                "write_available": "write" in scope.split(),
                "site_name": getattr(settings, "CRUDKIT_FRONTEND_CONFIG", {}).get("app_name", "CrudKit"),
            },
        )

    def post(self, request):
        redirect_uri = request.POST.get("redirect_uri")
        code_challenge = request.POST.get("code_challenge")
        state = request.POST.get("state", "")

        client, scope, error = self._validate_params(request)
        if error:
            return JsonResponse({"error": error}, status=400)

        if request.POST.get("action") == "deny":
            return http_redirect(_build_redirect_url(redirect_uri, error="access_denied", state=state))

        # `read` is always granted; `write` only when requested and ticked on the consent page.
        write = "write" in scope.split() and request.POST.get("write") == "on"
        auth_code = AuthorizationCode.objects.create(
            client=client,
            user=request.user,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            scopes="read write" if write else "read",
            expires_at=timezone.now() + AUTH_CODE_LIFETIME,
        )

        return http_redirect(_build_redirect_url(redirect_uri, code=auth_code.code, state=state))

    def _validate_params(self, request) -> tuple[OAuthClient | None, str | None, str | None]:
        params = request.GET if request.method == "GET" else request.POST
        client_id = params.get("client_id")
        redirect_uri = params.get("redirect_uri")
        code_challenge = params.get("code_challenge")
        response_type = params.get("response_type", "code")
        code_challenge_method = params.get("code_challenge_method", "S256")
        # No scope requested → offer everything this server supports.
        scope = " ".join(sorted({"read", *(params.get("scope") or " ".join(supported_scopes())).split()}))

        if not all([client_id, redirect_uri, code_challenge]):
            return None, None, "Missing required parameters: client_id, redirect_uri, code_challenge"

        if response_type != "code":
            return None, None, "Unsupported response_type, must be 'code'"

        if code_challenge_method != "S256":
            return None, None, "Unsupported code_challenge_method, must be 'S256'"

        try:
            client = OAuthClient.objects.get(client_id=client_id)
        except OAuthClient.DoesNotExist:
            return None, None, "Invalid client_id"

        if not client.is_active:
            return None, None, "Client is inactive"

        if not client.is_valid_redirect_uri(redirect_uri):
            return None, None, "Invalid redirect_uri"

        unsupported = set(scope.split()) - set(supported_scopes())
        if unsupported:
            return None, None, f"Unsupported scope: {' '.join(sorted(unsupported))}"

        return client, scope, None


def _issue_token_pair(client: OAuthClient, user, scopes: str, family_id=None) -> tuple[AccessToken, RefreshToken]:
    now = timezone.now()
    access_token = AccessToken.objects.create(
        client=client,
        user=user,
        scopes=scopes,
        expires_at=now + ACCESS_TOKEN_LIFETIME,
    )
    refresh_kwargs = {
        "client": client,
        "user": user,
        "scopes": scopes,
        "expires_at": now + REFRESH_TOKEN_LIFETIME,
    }
    if family_id is not None:
        refresh_kwargs["family_id"] = family_id
    refresh_token = RefreshToken.objects.create(**refresh_kwargs)
    return access_token, refresh_token


def _token_response(access_token: AccessToken, refresh_token: RefreshToken) -> JsonResponse:
    return JsonResponse(
        {
            "access_token": access_token.token,
            "token_type": "Bearer",
            "expires_in": int(ACCESS_TOKEN_LIFETIME.total_seconds()),
            "refresh_token": refresh_token.token,
            "refresh_token_expires_in": int(REFRESH_TOKEN_LIFETIME.total_seconds()),
            "scope": access_token.scopes,
        }
    )


@method_decorator(csrf_exempt, name="dispatch")
class TokenView(View):
    def post(self, request):
        grant_type = request.POST.get("grant_type")

        if grant_type == "authorization_code":
            return self._handle_authorization_code_grant(request)
        if grant_type == "refresh_token":
            return self._handle_refresh_token_grant(request)
        return JsonResponse({"error": "unsupported_grant_type"}, status=400)

    def _handle_authorization_code_grant(self, request):
        code = request.POST.get("code")
        redirect_uri = request.POST.get("redirect_uri")
        client_id = request.POST.get("client_id")
        code_verifier = request.POST.get("code_verifier")

        if not all([code, redirect_uri, client_id, code_verifier]):
            return JsonResponse({"error": "invalid_request"}, status=400)

        with transaction.atomic():
            try:
                auth_code = (
                    AuthorizationCode.objects.select_related("client", "user")
                    .select_for_update(of=("self",))
                    .get(code=code, client__client_id=client_id)
                )
            except AuthorizationCode.DoesNotExist:
                return JsonResponse({"error": "invalid_grant"}, status=400)

            if auth_code.is_used or auth_code.is_expired or not auth_code.user.is_active:
                return JsonResponse({"error": "invalid_grant"}, status=400)

            if auth_code.redirect_uri != redirect_uri:
                return JsonResponse({"error": "invalid_grant"}, status=400)

            if not auth_code.verify_code_challenge(code_verifier):
                return JsonResponse({"error": "invalid_grant"}, status=400)

            auth_code.is_used = True
            auth_code.save(update_fields=["is_used"])

        access_token, refresh_token = _issue_token_pair(auth_code.client, auth_code.user, auth_code.scopes)
        return _token_response(access_token, refresh_token)

    def _handle_refresh_token_grant(self, request):
        presented_token = request.POST.get("refresh_token")
        client_id = request.POST.get("client_id")
        requested_scope = request.POST.get("scope")

        if not all([presented_token, client_id]):
            return JsonResponse({"error": "invalid_request"}, status=400)

        with transaction.atomic():
            try:
                rt = (
                    RefreshToken.objects.select_related("client", "user")
                    .select_for_update(of=("self",))
                    .get(token=presented_token)
                )
            except RefreshToken.DoesNotExist:
                return JsonResponse({"error": "invalid_grant"}, status=400)

            if rt.client.client_id != client_id:
                return JsonResponse({"error": "invalid_client"}, status=400)

            if rt.is_revoked:
                rt.revoke_family()
                return JsonResponse({"error": "invalid_grant"}, status=400)

            if rt.is_expired:
                return JsonResponse({"error": "invalid_grant"}, status=400)

            if not rt.user.is_active:
                rt.revoke_family()
                return JsonResponse({"error": "invalid_grant"}, status=400)

            if not rt.client.is_active:
                return JsonResponse({"error": "invalid_client"}, status=400)

            granted_scopes = set(rt.scopes.split())
            if requested_scope is not None:
                requested_scopes = set(requested_scope.split())
                if not requested_scopes.issubset(granted_scopes):
                    return JsonResponse({"error": "invalid_scope"}, status=400)
                new_scopes = " ".join(sorted(requested_scopes))
            else:
                new_scopes = rt.scopes

            rt.revoked_at = timezone.now()
            rt.save(update_fields=["revoked_at"])

            access_token, new_rt = _issue_token_pair(rt.client, rt.user, new_scopes, family_id=rt.family_id)
            rt.replaced_by = new_rt
            rt.save(update_fields=["replaced_by"])

        return _token_response(access_token, new_rt)


class RegisterRateThrottle(AnonRateThrottle):
    scope = "crudkit_mcp_register"

    def get_rate(self):
        return self.THROTTLE_RATES.get(self.scope, "30/hour")


@method_decorator(csrf_exempt, name="dispatch")
class OAuthRegisterView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        client_name = request.data.get("client_name")
        redirect_uris = request.data.get("redirect_uris")

        if not client_name or not isinstance(client_name, str):
            return JsonResponse(
                {"error": "invalid_client_metadata", "error_description": "client_name is required"}, status=400
            )

        if not isinstance(redirect_uris, list) or not redirect_uris:
            return JsonResponse(
                {"error": "invalid_client_metadata", "error_description": "redirect_uris must be a non-empty list"},
                status=400,
            )

        if len(redirect_uris) > 10:
            return JsonResponse(
                {"error": "invalid_client_metadata", "error_description": "Too many redirect_uris (max 10)"}, status=400
            )

        for uri in redirect_uris:
            if not isinstance(uri, str):
                return JsonResponse(
                    {"error": "invalid_client_metadata", "error_description": "Each redirect_uri must be a string"},
                    status=400,
                )
            if not settings.DEBUG and not uri.startswith("https://"):
                # RFC 8252: allow HTTP for loopback redirect URIs (native app OAuth flows)
                is_loopback = uri.startswith(("http://127.0.0.1", "http://[::1]", "http://localhost"))
                if not is_loopback:
                    return JsonResponse(
                        {"error": "invalid_client_metadata", "error_description": "redirect_uris must use HTTPS"},
                        status=400,
                    )

        client = OAuthClient.objects.create(
            client_name=client_name,
            redirect_uris=redirect_uris,
        )

        return JsonResponse(
            {
                "client_id": client.client_id,
                "client_name": client.client_name,
                "redirect_uris": client.redirect_uris,
                "client_id_issued_at": calendar.timegm(client.created_at.utctimetuple()),
            },
            status=201,
        )
