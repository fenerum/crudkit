"""User-profile indirection for CrudKit.

CrudKit needs two things from the consuming project's notion of a user
profile: a preferred language and avatar images. Projects provide them by
pointing ``CRUDKIT_USER_PROFILE_ADAPTER`` at a class with the same interface
as ``DefaultUserProfileAdapter``.
"""

from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.module_loading import import_string


class DefaultUserProfileAdapter:
    def get(self, user) -> dict[str, Any]:
        return {"preferred_language": "en", "object_images": []}

    def set_language(self, user, preferred_language: str) -> None:
        pass


def get_user_profile_adapter():
    adapter_path = getattr(settings, "CRUDKIT_USER_PROFILE_ADAPTER", None)
    if adapter_path:
        return import_string(adapter_path)()
    return DefaultUserProfileAdapter()


def get_object_images(obj) -> list:
    """Images for any object: its own ``get_object_images()`` if it defines
    one, the profile adapter for user instances, otherwise none."""
    if getattr(obj, "get_object_images", None):
        return obj.get_object_images() or []
    if isinstance(obj, get_user_model()):
        return get_user_profile_adapter().get(obj).get("object_images") or []
    return []
