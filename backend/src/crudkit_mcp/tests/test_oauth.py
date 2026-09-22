import base64
import hashlib
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from crudkit_mcp.models import AccessToken, AuthorizationCode, OAuthClient, RefreshToken


class OAuthClientModelTest(TestCase):
    def test_valid_redirect_uri(self):
        client = OAuthClient.objects.create(
            client_name="Test",
            redirect_uris=["http://localhost:3000/callback", "http://example.com/callback"],
        )
        self.assertTrue(client.is_valid_redirect_uri("http://localhost:3000/callback"))
        self.assertTrue(client.is_valid_redirect_uri("http://example.com/callback"))
        self.assertFalse(client.is_valid_redirect_uri("http://evil.com/callback"))


class PKCEVerificationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="testpass")
        self.client_obj = OAuthClient.objects.create(
            client_name="Test",
            redirect_uris=["http://localhost/callback"],
        )

    def test_verify_code_challenge(self):
        code_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

        auth_code = AuthorizationCode.objects.create(
            client=self.client_obj,
            user=self.user,
            redirect_uri="http://localhost/callback",
            code_challenge=code_challenge,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.assertTrue(auth_code.verify_code_challenge(code_verifier))
        self.assertFalse(auth_code.verify_code_challenge("wrong_verifier"))


class AuthorizeViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="testpass")
        self.oauth_client = OAuthClient.objects.create(
            client_name="Test App",
            redirect_uris=["http://localhost:3000/callback"],
        )
        self.http_client = Client()
        self.http_client.login(username="testuser", password="testpass")

    def test_get_authorize_renders_consent(self):
        response = self.http_client.get(
            "/api/v1/oauth/authorize/",
            {
                "client_id": self.oauth_client.client_id,
                "redirect_uri": "http://localhost:3000/callback",
                "code_challenge": "test_challenge",
                "state": "test_state",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test App")

    def test_get_authorize_missing_params(self):
        response = self.http_client.get("/api/v1/oauth/authorize/", {"client_id": "missing"})
        self.assertEqual(response.status_code, 400)

    def test_post_authorize_creates_code(self):
        response = self.http_client.post(
            "/api/v1/oauth/authorize/",
            {
                "client_id": self.oauth_client.client_id,
                "redirect_uri": "http://localhost:3000/callback",
                "code_challenge": "test_challenge",
                "state": "test_state",
                "action": "allow",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("code=", response.url)
        self.assertEqual(AuthorizationCode.objects.count(), 1)

    def test_post_authorize_deny(self):
        response = self.http_client.post(
            "/api/v1/oauth/authorize/",
            {
                "client_id": self.oauth_client.client_id,
                "redirect_uri": "http://localhost:3000/callback",
                "code_challenge": "test_challenge",
                "state": "test_state",
                "action": "deny",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("error=access_denied", response.url)

    def test_state_with_special_chars_is_encoded(self):
        response = self.http_client.post(
            "/api/v1/oauth/authorize/",
            {
                "client_id": self.oauth_client.client_id,
                "redirect_uri": "http://localhost:3000/callback",
                "code_challenge": "test_challenge",
                "state": "a=1&b=2",
                "action": "allow",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("state=a%3D1%26b%3D2", response.url)

    def test_invalid_response_type_rejected(self):
        response = self.http_client.get(
            "/api/v1/oauth/authorize/",
            {
                "client_id": self.oauth_client.client_id,
                "redirect_uri": "http://localhost:3000/callback",
                "code_challenge": "test_challenge",
                "response_type": "token",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("response_type", response.json()["error"])

    def test_invalid_code_challenge_method_rejected(self):
        response = self.http_client.get(
            "/api/v1/oauth/authorize/",
            {
                "client_id": self.oauth_client.client_id,
                "redirect_uri": "http://localhost:3000/callback",
                "code_challenge": "test_challenge",
                "code_challenge_method": "plain",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("code_challenge_method", response.json()["error"])


class TokenViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="testpass")
        self.oauth_client = OAuthClient.objects.create(
            client_name="Test App",
            redirect_uris=["http://localhost:3000/callback"],
        )
        self.code_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(self.code_verifier.encode("ascii")).digest()
        self.code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        self.auth_code = AuthorizationCode.objects.create(
            client=self.oauth_client,
            user=self.user,
            redirect_uri="http://localhost:3000/callback",
            code_challenge=self.code_challenge,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def test_token_exchange_success(self):
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "authorization_code",
                "code": self.auth_code.code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": self.oauth_client.client_id,
                "code_verifier": self.code_verifier,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "Bearer")
        self.assertEqual(AccessToken.objects.count(), 1)

    def test_token_exchange_wrong_verifier(self):
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "authorization_code",
                "code": self.auth_code.code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": self.oauth_client.client_id,
                "code_verifier": "wrong_verifier",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_grant")

    def test_token_exchange_expired_code(self):
        self.auth_code.expires_at = timezone.now() - timedelta(minutes=1)
        self.auth_code.save()
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "authorization_code",
                "code": self.auth_code.code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": self.oauth_client.client_id,
                "code_verifier": self.code_verifier,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_token_exchange_used_code(self):
        self.auth_code.is_used = True
        self.auth_code.save()
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "authorization_code",
                "code": self.auth_code.code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": self.oauth_client.client_id,
                "code_verifier": self.code_verifier,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_unsupported_grant_type(self):
        response = self.client.post(
            "/api/v1/oauth/token/",
            {"grant_type": "client_credentials"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "unsupported_grant_type")

    def test_token_endpoint_exempt_from_csrf(self):
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "authorization_code",
                "code": self.auth_code.code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": self.oauth_client.client_id,
                "code_verifier": self.code_verifier,
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_inactive_client_token_rejected_at_use(self):
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "authorization_code",
                "code": self.auth_code.code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": self.oauth_client.client_id,
                "code_verifier": self.code_verifier,
            },
        )
        self.assertEqual(response.status_code, 200)
        access_token = response.json()["access_token"]

        self.oauth_client.is_active = False
        self.oauth_client.save()

        response = self.client.post(
            "/api/v1/mcp/",
            data='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        self.assertEqual(response.status_code, 401)


class OAuthBearerAuthenticationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="testpass")
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

    def test_valid_token_authenticates(self):
        response = self.client.post(
            "/api/v1/mcp/",
            data='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_expired_token_rejected(self):
        self.token.expires_at = timezone.now() - timedelta(hours=1)
        self.token.save()
        response = self.client.post(
            "/api/v1/mcp/",
            data='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_token_rejected(self):
        response = self.client.post(
            "/api/v1/mcp/",
            data='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer invalid_token_here",
        )
        self.assertEqual(response.status_code, 401)

    def test_no_auth_header_rejected(self):
        response = self.client.post(
            "/api/v1/mcp/",
            data='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_www_authenticate_header_on_401(self):
        response = self.client.post(
            "/api/v1/mcp/",
            data='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("resource_metadata", response["WWW-Authenticate"])


class MetadataEndpointTest(TestCase):
    def test_authorization_server_metadata(self):
        response = self.client.get("/.well-known/oauth-authorization-server")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["issuer"], "http://testserver")
        self.assertIn("authorization_endpoint", data)
        self.assertIn("token_endpoint", data)
        self.assertIn("registration_endpoint", data)
        self.assertEqual(data["response_types_supported"], ["code"])
        self.assertEqual(data["grant_types_supported"], ["authorization_code", "refresh_token"])
        self.assertEqual(data["code_challenge_methods_supported"], ["S256"])

    def test_protected_resource_metadata(self):
        response = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("resource", data)
        self.assertIn("authorization_servers", data)
        self.assertEqual(data["bearer_methods_supported"], ["header"])


@override_settings(DEBUG=True)
class OAuthRegisterViewTest(TestCase):
    def test_register_success(self):
        response = self.client.post(
            "/api/v1/oauth/register/",
            data={"client_name": "My App", "redirect_uris": ["http://localhost:3000/callback"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("client_id", data)
        self.assertEqual(data["client_name"], "My App")
        self.assertEqual(data["redirect_uris"], ["http://localhost:3000/callback"])
        self.assertIn("client_id_issued_at", data)
        self.assertEqual(OAuthClient.objects.count(), 1)

    def test_register_missing_client_name(self):
        response = self.client.post(
            "/api/v1/oauth/register/",
            data={"redirect_uris": ["http://localhost:3000/callback"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_register_missing_redirect_uris(self):
        response = self.client.post(
            "/api/v1/oauth/register/",
            data={"client_name": "My App"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_register_too_many_redirect_uris(self):
        response = self.client.post(
            "/api/v1/oauth/register/",
            data={"client_name": "My App", "redirect_uris": [f"http://localhost:{i}/cb" for i in range(11)]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_register_empty_redirect_uris(self):
        response = self.client.post(
            "/api/v1/oauth/register/",
            data={"client_name": "My App", "redirect_uris": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(DEBUG=False)
    def test_register_rejects_non_https_in_production(self):
        response = self.client.post(
            "/api/v1/oauth/register/",
            data={"client_name": "My App", "redirect_uris": ["http://example.com/callback"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("HTTPS", response.json()["error_description"])

    def test_register_allows_loopback_http(self):
        for uri in ["http://127.0.0.1:3000/callback", "http://localhost:3000/callback", "http://[::1]:3000/callback"]:
            response = self.client.post(
                "/api/v1/oauth/register/",
                data={"client_name": "CLI App", "redirect_uris": [uri]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201, f"Expected 201 for {uri}")

    def test_register_csrf_exempt(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            "/api/v1/oauth/register/",
            data={"client_name": "My App", "redirect_uris": ["http://localhost:3000/callback"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)


class RefreshTokenGrantTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="testpass")
        self.oauth_client = OAuthClient.objects.create(
            client_name="Test App",
            redirect_uris=["http://localhost:3000/callback"],
        )
        self.code_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(self.code_verifier.encode("ascii")).digest()
        self.code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def _exchange_code(self):
        auth_code = AuthorizationCode.objects.create(
            client=self.oauth_client,
            user=self.user,
            redirect_uri="http://localhost:3000/callback",
            code_challenge=self.code_challenge,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "authorization_code",
                "code": auth_code.code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": self.oauth_client.client_id,
                "code_verifier": self.code_verifier,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_code_exchange_returns_refresh_token(self):
        data = self._exchange_code()
        self.assertIn("refresh_token", data)
        self.assertIn("refresh_token_expires_in", data)
        self.assertEqual(data["refresh_token_expires_in"], 90 * 24 * 60 * 60)
        self.assertEqual(RefreshToken.objects.count(), 1)

    def test_refresh_grant_success(self):
        initial = self._exchange_code()
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": initial["refresh_token"],
                "client_id": self.oauth_client.client_id,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertNotEqual(data["access_token"], initial["access_token"])
        self.assertNotEqual(data["refresh_token"], initial["refresh_token"])
        self.assertEqual(data["token_type"], "Bearer")

    def test_refresh_grant_rotates_old_refresh_revoked(self):
        initial = self._exchange_code()
        self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": initial["refresh_token"],
                "client_id": self.oauth_client.client_id,
            },
        )
        old_rt = RefreshToken.objects.get(token=initial["refresh_token"])
        self.assertIsNotNone(old_rt.revoked_at)
        self.assertIsNotNone(old_rt.replaced_by)
        self.assertEqual(old_rt.replaced_by.family_id, old_rt.family_id)
        self.assertIsNone(old_rt.replaced_by.revoked_at)

    def test_refresh_grant_reuse_revokes_family(self):
        initial = self._exchange_code()
        first = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": initial["refresh_token"],
                "client_id": self.oauth_client.client_id,
            },
        )
        self.assertEqual(first.status_code, 200)
        rt2 = first.json()["refresh_token"]

        replay = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": initial["refresh_token"],
                "client_id": self.oauth_client.client_id,
            },
        )
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(replay.json()["error"], "invalid_grant")

        rt2_obj = RefreshToken.objects.get(token=rt2)
        self.assertIsNotNone(rt2_obj.revoked_at)

    def test_refresh_grant_expired_refresh_token_rejected(self):
        initial = self._exchange_code()
        rt = RefreshToken.objects.get(token=initial["refresh_token"])
        rt.expires_at = timezone.now() - timedelta(minutes=1)
        rt.save()
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": initial["refresh_token"],
                "client_id": self.oauth_client.client_id,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_grant")

    def test_refresh_grant_client_mismatch_rejected(self):
        initial = self._exchange_code()
        other_client = OAuthClient.objects.create(
            client_name="Other App",
            redirect_uris=["http://localhost:4000/callback"],
        )
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": initial["refresh_token"],
                "client_id": other_client.client_id,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_client")

    def test_refresh_grant_inactive_client_rejected(self):
        initial = self._exchange_code()
        self.oauth_client.is_active = False
        self.oauth_client.save()
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": initial["refresh_token"],
                "client_id": self.oauth_client.client_id,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_client")

    def test_refresh_grant_scope_cannot_widen(self):
        initial = self._exchange_code()
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": initial["refresh_token"],
                "client_id": self.oauth_client.client_id,
                "scope": "read write",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_scope")

    def test_refresh_grant_missing_params(self):
        response = self.client.post(
            "/api/v1/oauth/token/",
            {"grant_type": "refresh_token"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_request")

    def test_refresh_grant_unknown_token_rejected(self):
        response = self.client.post(
            "/api/v1/oauth/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": "does_not_exist",
                "client_id": self.oauth_client.client_id,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_grant")


class MetadataUrlsTest(TestCase):
    def test_endpoints_follow_url_conf(self):
        data = self.client.get("/.well-known/oauth-authorization-server").json()
        self.assertEqual(data["issuer"], "http://testserver")
        self.assertEqual(data["authorization_endpoint"], "http://testserver/api/v1/oauth/authorize/")
        self.assertEqual(data["token_endpoint"], "http://testserver/api/v1/oauth/token/")
        self.assertEqual(data["registration_endpoint"], "http://testserver/api/v1/oauth/register/")
        self.assertEqual(data["scopes_supported"], ["read"])

        data = self.client.get("/.well-known/oauth-protected-resource").json()
        self.assertEqual(data["resource"], "http://testserver/api/v1/mcp/")
        self.assertEqual(data["authorization_servers"], ["http://testserver"])

    def test_path_suffixed_discovery(self):
        response = self.client.get("/.well-known/oauth-protected-resource/api/v1/mcp")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/.well-known/oauth-authorization-server/api/v1/mcp")
        self.assertEqual(response.status_code, 200)

    @override_settings(CRUDKIT_MCP_BASE_URL="https://crm.example.com/")
    def test_base_url_override(self):
        data = self.client.get("/.well-known/oauth-authorization-server").json()
        self.assertEqual(data["issuer"], "https://crm.example.com")
        self.assertEqual(data["token_endpoint"], "https://crm.example.com/api/v1/oauth/token/")

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_write_scope_advertised_when_enabled(self):
        data = self.client.get("/.well-known/oauth-authorization-server").json()
        self.assertEqual(data["scopes_supported"], ["read", "write"])


class AuthorizeScopeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="testpass")
        self.oauth_client = OAuthClient.objects.create(
            client_name="Test App",
            redirect_uris=["http://localhost:3000/callback"],
        )
        self.client.login(username="testuser", password="testpass")

    def _authorize(self, **extra):
        return self.client.post(
            "/api/v1/oauth/authorize/",
            {
                "client_id": self.oauth_client.client_id,
                "redirect_uri": "http://localhost:3000/callback",
                "code_challenge": "test_challenge",
                "action": "allow",
                **extra,
            },
        )

    def test_default_scope_is_read(self):
        self.assertEqual(self._authorize().status_code, 302)
        self.assertEqual(AuthorizationCode.objects.get().scopes, "read")

    def test_write_scope_rejected_when_disabled(self):
        response = self._authorize(scope="read write")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AuthorizationCode.objects.exists())

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_write_needs_checkbox(self):
        self._authorize()
        self.assertEqual(AuthorizationCode.objects.get().scopes, "read")

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_write_granted_when_ticked(self):
        self._authorize(write="on")
        self.assertEqual(AuthorizationCode.objects.get().scopes, "read write")

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_read_always_granted(self):
        self._authorize(scope="write", write="on")
        self.assertEqual(AuthorizationCode.objects.get().scopes, "read write")

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_write_not_granted_unless_requested(self):
        self._authorize(scope="read", write="on")
        self.assertEqual(AuthorizationCode.objects.get().scopes, "read")

    def _consent_page(self, **extra):
        return self.client.get(
            "/api/v1/oauth/authorize/",
            {
                "client_id": self.oauth_client.client_id,
                "redirect_uri": "http://localhost:3000/callback",
                "code_challenge": "test_challenge",
                **extra,
            },
        )

    @override_settings(CRUDKIT_MCP_WRITE_ENABLED=True)
    def test_consent_page_offers_write_checkbox(self):
        self.assertContains(self._consent_page(), 'name="write"')
        self.assertNotContains(self._consent_page(scope="read"), 'name="write"')

    def test_consent_page_hides_write_when_disabled(self):
        response = self._consent_page()
        self.assertContains(response, "View records")
        self.assertNotContains(response, 'name="write"')
