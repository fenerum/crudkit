from django.contrib import admin

from crudkit_mcp.models import AccessToken, AuthorizationCode, OAuthClient, RefreshToken


@admin.register(OAuthClient)
class OAuthClientAdmin(admin.ModelAdmin):
    list_display = ["client_name", "client_id", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["client_name", "client_id"]
    readonly_fields = ["client_id", "created_at"]


@admin.register(AuthorizationCode)
class AuthorizationCodeAdmin(admin.ModelAdmin):
    list_display = ["user", "client", "is_used", "expires_at", "created_at"]
    list_filter = ["is_used", "client"]
    search_fields = ["user__username", "client__client_name"]
    readonly_fields = ["code", "code_challenge", "created_at"]


@admin.register(AccessToken)
class AccessTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "client", "scopes", "expires_at", "created_at"]
    list_filter = ["client"]
    search_fields = ["user__username", "client__client_name"]
    readonly_fields = ["token", "created_at"]


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "client", "scopes", "expires_at", "revoked_at", "created_at"]
    list_filter = ["client"]
    search_fields = ["user__username", "client__client_name", "family_id"]
    readonly_fields = ["token", "family_id", "replaced_by", "created_at"]
