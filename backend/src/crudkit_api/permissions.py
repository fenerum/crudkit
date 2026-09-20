from rest_framework.permissions import BasePermission

from crudkit.authorization import get_permission_action, has_model_permission, has_object_permission


class CrudKitModelPermissions(BasePermission):
    def has_permission(self, request, view):
        if not getattr(request.user, "is_authenticated", False):
            return False
        # Set by DRF on rest_framework.routers.APIRootView (inherited by
        # CrudKitAPIRootView) and on SchemaView: views with no model opting out
        # of model permissions. DjangoModelPermissions honours it the same way.
        if getattr(view, "_ignore_model_permissions", False):
            return True
        queryset = getattr(view, "queryset", None)
        if queryset is None:
            return False
        action = get_permission_action(request.method, getattr(view, "action", None))
        return has_model_permission(request.user, queryset.model, action)

    def has_object_permission(self, request, view, obj):
        action = get_permission_action(request.method, getattr(view, "action", None))
        return has_object_permission(request.user, obj, action)
