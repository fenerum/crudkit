from django.contrib import admin

from crudkit_assistant.models import AssistantConversation, AssistantProposal


@admin.register(AssistantProposal)
class AssistantProposalAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "client", "kind", "status", "label", "created_at", "confirmed_at")
    list_filter = ("source", "kind", "status")
    search_fields = ("session_key", "label", "id")
    readonly_fields = (
        "session_key",
        "source",
        "client",
        "target_content_type",
        "target_object_id",
        "kind",
        "label",
        "reasoning",
        "payload",
        "outcome",
        "confirmed_at",
        "confirmed_by",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "status",
    )


@admin.register(AssistantConversation)
class AssistantConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_by", "updated_at")
    search_fields = ("title", "id")
    readonly_fields = ("session_key", "messages", "transcript", "created_at", "created_by", "updated_at", "updated_by")
