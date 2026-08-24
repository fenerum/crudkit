from django.conf import settings as dj_settings
from django.contrib.auth import authenticate, logout
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from crudkit.profile import get_user_profile_adapter


class UserSerializer(serializers.Serializer):
    id = serializers.ReadOnlyField(source="pk")
    username = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()

    def get_username(self, user):
        return user.get_username()

    def get_email(self, user):
        return getattr(user, "email", "")

    def get_first_name(self, user):
        return getattr(user, "first_name", "")

    def get_last_name(self, user):
        return getattr(user, "last_name", "")


def _is_safe_image_path(img):
    """Reject anything that isn't a relative /media/... or absolute http(s)://
    URL so we never feed user-controlled javascript:/data:/etc URIs into
    request.build_absolute_uri or out to the frontend."""
    if not isinstance(img, str) or not img:
        return False
    if img.startswith("/media/") or img.startswith("/static/"):
        return True
    if img.startswith(("http://", "https://")):
        return True
    return False


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(username=username, password=password)

        if user:
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": UserSerializer(user).data,
                }
            )

        return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_value = request.data.get("refresh")
        if refresh_value:
            try:
                refresh = RefreshToken(refresh_value)
                blacklist = getattr(refresh, "blacklist", None)
                if blacklist:
                    blacklist()
            except TokenError:
                pass
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = UserSerializer(request.user).data
        profile_data = get_user_profile_adapter().get(request.user)
        data["preferred_language"] = profile_data.get("preferred_language") or "en"
        images = profile_data.get("object_images") or []
        safe_images = [img for img in images if _is_safe_image_path(img)]
        data["object_images"] = [request.build_absolute_uri(img) if img.startswith("/") else img for img in safe_images]
        data["assistant"] = {
            "name": getattr(dj_settings, "CRUDKIT_ASSISTANT_NAME", "Assistant"),
            "avatar_url": getattr(dj_settings, "CRUDKIT_ASSISTANT_AVATAR_URL", ""),
        }
        return Response(data)

    def patch(self, request):
        preferred_language = request.data.get("preferred_language")
        if preferred_language is not None:
            get_user_profile_adapter().set_language(request.user, preferred_language)
        return self.get(request)
