"""Context processors for the SPA shell template."""

import json

from django.conf import settings
from django.utils.safestring import mark_safe


def crudkit_config(request):
    config = getattr(settings, "CRUDKIT_FRONTEND_CONFIG", {})
    # Escape "<" so "</script>" in values cannot break out of the script tag.
    payload = json.dumps(config).replace("<", "\\u003c")
    # settings.STATIC_URL is already "/"-prefixed by Django on access.
    static_url = json.dumps(settings.STATIC_URL).replace("<", "\\u003c")
    return {
        "crudkit_config_json": mark_safe(payload),
        "crudkit_app_name": config.get("app_name", "CrudKit"),
        "crudkit_static_url_json": mark_safe(static_url),
    }
