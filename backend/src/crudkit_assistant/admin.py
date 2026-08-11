from django.contrib import admin

from crudkit_assistant.models import AssistantProposal


@admin.register(AssistantProposal)
class AssistantProposalAdmin(admin.ModelAdmin):
    list_display = ("id", "session_key", "kind", "status", "label", "created_at", "confirmed_at")
    list_filter = ("kind", "status")
    search_fields = ("session_key", "label", "id")
    readonly_fields = (
        "session_key",
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
