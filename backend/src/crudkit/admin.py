from django.contrib import admin

from .models import ExchangeRate


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    """Admin configuration for ExchangeRate model."""

    list_display = ("currency", "rate", "from_date", "to_date", "created_at")
    list_filter = ("currency", "from_date")
    search_fields = ("currency",)
    ordering = ("-from_date", "currency")
    date_hierarchy = "from_date"

    fieldsets = (
        (
            None,
            {
                "fields": ("currency", "rate"),
            },
        ),
        (
            "Date Range",
            {
                "fields": ("from_date", "to_date"),
                "description": 'Specify the date range for which this exchange rate is valid. Leave "to_date" blank for rates that apply indefinitely.',
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Set the created_by and updated_by fields when saving via admin."""
        if not change:  # New object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
