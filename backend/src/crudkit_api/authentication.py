from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from crudkit.profile import get_user_profile_adapter


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]


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
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                    },
                }
            )

        return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.conf import settings as dj_settings

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
