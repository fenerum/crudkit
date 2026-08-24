from rest_framework.permissions import BasePermission

from crudkit.authorization import get_permission_action, has_model_permission, has_object_permission


class CrudKitModelPermissions(BasePermission):
    def has_permission(self, request, view):
        queryset = getattr(view, "queryset", None)
        if queryset is None:
            return False
        action = get_permission_action(request.method, getattr(view, "action", None))
        return has_model_permission(request.user, queryset.model, action)

    def has_object_permission(self, request, view, obj):
        action = get_permission_action(request.method, getattr(view, "action", None))
        return has_object_permission(request.user, obj, action)
