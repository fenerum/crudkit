from django.urls import include, path
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView

from crudkit.utils import get_model_types
from crudkit_api.authentication import LoginView, LogoutView, UserProfileView
from crudkit_api.serializers import get_serializer
from crudkit_api.views import GenericViewSet, SearchViewSet, WidgetsViewSet

# ViewSets define the view behavior.


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
# router.register(r"users", UserViewSet)

for type_id, mdl in get_model_types().items():
    cls = get_serializer(mdl)

    router.register(
        r"%s" % type_id,
        type("%sViewSet" % mdl.__name__, (GenericViewSet,), {"queryset": mdl.objects.all(), "serializer_class": cls}),
        basename=mdl.__name__.lower(),
    )
router.register(r"search", SearchViewSet, basename="search")
router.register(r"widgets", WidgetsViewSet, basename="widgets")


# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("", include(router.urls)),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    # JWT Authentication endpoints
    path("token/", LoginView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # User profile endpoint
    path("user/me/", UserProfileView.as_view(), name="user_profile"),
]
