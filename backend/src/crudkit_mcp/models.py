import base64
import hashlib
import hmac
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_client_id():
    return secrets.token_urlsafe(32)


def generate_token():
    return secrets.token_urlsafe(64)


def generate_code():
    return secrets.token_urlsafe(48)


class OAuthClient(models.Model):
    client_id = models.CharField(max_length=128, unique=True, default=generate_client_id)
    client_name = models.CharField(max_length=256)
    redirect_uris = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid_redirect_uri(self, uri: str) -> bool:
        return uri in self.redirect_uris

    def __str__(self):
        return self.client_name

    class Meta:
        ordering = ["client_name"]


class AuthorizationCode(models.Model):
    code = models.CharField(max_length=128, unique=True, default=generate_code)
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    redirect_uri = models.URLField(max_length=512)
    code_challenge = models.CharField(max_length=256)
    scopes = models.CharField(max_length=512, default="read")
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def verify_code_challenge(self, code_verifier: str) -> bool:
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return hmac.compare_digest(self.code_challenge, expected)

    def __str__(self):
        return f"AuthCode for {self.user} via {self.client}"

    class Meta:
        ordering = ["-created_at"]


class AccessToken(models.Model):
    token = models.CharField(max_length=128, unique=True, default=generate_token)
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    scopes = models.CharField(max_length=512, default="read")
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"Token for {self.user} via {self.client}"

    class Meta:
        ordering = ["-created_at"]


class RefreshToken(models.Model):
    token = models.CharField(max_length=128, unique=True, default=generate_token)
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    scopes = models.CharField(max_length=512, default="read")
    family_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    replaced_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replaces",
    )
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_active(self) -> bool:
        return not self.is_expired and not self.is_revoked

    def revoke_family(self) -> int:
        return RefreshToken.objects.filter(family_id=self.family_id, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )

    def __str__(self):
        return f"RefreshToken for {self.user} via {self.client}"

    class Meta:
        ordering = ["-created_at"]
