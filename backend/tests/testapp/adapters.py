"""In-memory user-profile adapter used to exercise CRUDKIT_USER_PROFILE_ADAPTER."""

from typing import ClassVar


class InMemoryUserProfileAdapter:
    # Class-level stores so state survives the per-request instantiation done
    # by get_user_profile_adapter(). Tests must reset() between runs.
    languages: ClassVar[dict] = {}
    images: ClassVar[dict] = {}

    @classmethod
    def reset(cls) -> None:
        cls.languages.clear()
        cls.images.clear()

    def get(self, user) -> dict:
        return {
            "preferred_language": self.languages.get(user.pk, "en"),
            "object_images": self.images.get(user.pk, []),
        }

    def set_language(self, user, preferred_language: str) -> None:
        self.languages[user.pk] = preferred_language
