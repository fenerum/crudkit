import re

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.exceptions import ValidationError
from django.db import connection, models, reset_queries, transaction
from django.db.models import ProtectedError, Q
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from crudkit.authorization import (
    get_authorized_queryset,
    get_permission_action,
    has_action_permission,
    has_model_permission,
)
from crudkit.models import BaseCrudKitModel, ChangeLog
from crudkit.utils import get_model_types
from crudkit_api.metadata import build_model_metadata
from crudkit_api.permissions import CrudKitModelPermissions
from crudkit_api.serializers import GenericSerializer, get_serializer


class GenericViewSet(viewsets.ModelViewSet):
    permission_classes = [CrudKitModelPermissions]

    def get_queryset(self):
        queryset = super().get_queryset()
        action = get_permission_action(self.request.method, getattr(self, "action", None))
        return get_authorized_queryset(self.request.user, queryset, action)

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        if hasattr(self.queryset.model, "deleted") and not self.request.GET.get("deleted", False):
            queryset = queryset.filter(deleted=False)
        search = self.request.GET.get("_q", False)
        if search:
            search_filters = Q()
            for field in self.queryset.model.CrudKitSettings.search_fields:
                search_filters = search_filters | (Q(**{f"{field}__icontains": search.strip()}))
            queryset = queryset.filter(search_filters)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer: GenericSerializer):
        serializer.initial_instance = self.initial_instance
        instance = serializer.save()
        ChangeLog.objects.create_from_objects(None, instance)

    @transaction.atomic
    def perform_update(self, serializer: GenericSerializer):
        old_object = self.get_object()
        serializer.save()
        ChangeLog.objects.create_from_objects(old_object, serializer.instance)

    @transaction.atomic
    def perform_destroy(self, instance: BaseCrudKitModel):
        ChangeLog.objects.create_from_objects(instance, None)
        instance.soft_delete()

    def create(self, request, *args, **kwargs):
        self.initial_instance = self.queryset.model.from_query_params(
            self.request.GET,
            {
                "created_by": request.user,
                "updated_by": request.user,
            },
        )
        return super().create(request, *args, **kwargs)

    def get_serializer_class(self, fields="__all__"):
        return get_serializer(self.queryset.model, fields=fields)

    def get_fields(self, request):
        return request.GET.get("_fields").split(",") if request.GET.get("_fields") else []

    def list(self, request, *args, **kwargs):
        # Reset query stats
        reset_queries()
        # Run your query here
        queryset = self.filter_queryset(self.get_queryset())

        fields = self.get_fields(request)

        # Get all fields that are prefetchable or joinable, except reverse relations
        prefetchable_fields = [
            f.name
            for f in queryset.model._meta.get_fields()
            if f.is_relation
            and not hasattr(f, "related_name")
            and type(f) is not GenericForeignKey
            and (not fields or f.name in fields)
        ]

        queryset = queryset.prefetch_related(
            *(
                (
                    "created_by__user_permissions",
                    "created_by__groups",
                    "updated_by__user_permissions",
                    "updated_by__groups",
                )
                if queryset.model is not get_user_model()
                else []
            ),
            *prefetchable_fields,
        )

        # Always use pagination when it's enabled in settings
        page = self.paginate_queryset(queryset)
        if page is not None:
            # Process each paginated object individually to ensure proper currency serialization
            data = []
            serializer_class = self.get_serializer_class()

            for obj in page:
                # Store the current object being processed in the request for the serializer to access
                # This is needed for MoneyField serialization to get the correct currency
                self.request._current_object_for_serialization = obj
                serializer = serializer_class(obj, context={"request": self.request})
                data.append(serializer.data)

            response = self.get_paginated_response(data)
            response.headers["X-Query-Count"] = str(len(connection.queries))
            return response

        # Fallback for when pagination is disabled
        # Serialize with special handling for currency fields in list views
        data = []
        serializer_class = self.get_serializer_class()

        # Process each object individually to ensure proper currency serialization
        for obj in queryset:
            # Store the current object being processed in the request for the serializer to access
            self.request._current_object_for_serialization = obj
            serializer = serializer_class(obj, context={"request": self.request})
            data.append(serializer.data)

        return Response(data, headers={"X-Query-Count": len(connection.queries)})

    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @action(["POST"], detail=True, url_path="merge")
    def merge(self, request, pk=None):
        post_data = request.data
        try:
            with transaction.atomic():
                to_stay_obj = self.get_object()
                other_objects = self.get_queryset().filter(id__in=post_data.pop("merge")).exclude(id=to_stay_obj.id)

                if not all([x.TYPE_ID == to_stay_obj.TYPE_ID for x in other_objects]):
                    raise Exception(
                        "Cannot merge objects of different types %s"
                        % ([x.TYPE_ID for x in other_objects] + [to_stay_obj.TYPE_ID])
                    )
                if not other_objects:
                    raise Exception("No objects to merge")
                if to_stay_obj in other_objects:
                    raise Exception("Cannot merge the same object")

                merge_fields = post_data
                objects_by_id = {obj.id: obj for obj in [to_stay_obj, *other_objects]}

                for field, value in merge_fields.items():
                    if field not in ["id"]:
                        new_value = getattr(objects_by_id[value], field)
                        setattr(to_stay_obj, field, new_value)
                to_stay_obj.save()

                for to_be_deleted_object in other_objects:
                    to_be_deleted_object.delete_and_merge_with(to_stay_obj)

                messages = ([mark_safe(f"{to_stay_obj} merged. <a href='{to_stay_obj.id}'>View</a>")],)
                return Response({"messages": messages, "redirect": to_stay_obj.id})
        except (ValidationError, ProtectedError) as e:
            return Response({"errors": [str(e)]}, status=400)

    @action(["POST"], detail=True, url_path="action")
    def call_action(self, request, pk=None):
        instance = self.get_object()
        action_name = request.data.get("action")

        if action_name not in instance._actions:
            return Response({"error": f"Action {action_name} not found"}, status=400)
        if not has_action_permission(request.user, instance, action_name):
            raise PermissionDenied
        response = instance._actions[action_name](self.request)
        if isinstance(response, HttpResponseRedirect):
            return Response({"redirect": response.url})
        if isinstance(response, models.Model):
            return Response({"redirect": response.id})
        return response

    @action(detail=False, url_path="initial")
    def initial_data(self, request):
        instance = self.queryset.model.from_query_params(
            self.request.GET,
            {
                "created_by": request.user,
                "updated_by": request.user,
            },
        )

        return Response(
            {
                "fields": {
                    field: value
                    for field, value in self.serializer_class(instance).data.items()
                    if field in getattr(self.queryset.model.CrudKitSettings, "allowed_prefills", [])
                }
            }
        )

    @action(detail=False)
    def metadata(self, request):
        return Response(build_model_metadata(self.queryset.model))


CRM_TYPE_REGEX = re.compile(r"[A-Z]{3}")


class SearchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        query = request.GET.get("q")
        if not query:
            return Response({"results": []})

        # Try getting
        results = []

        if len(query) > 3 and CRM_TYPE_REGEX.match(query) and ":" in query:
            search_type, query = query.split(":")
            possible_searches = [
                mdl
                for mdl in get_model_types().values()
                if hasattr(mdl, "CrudKitSettings") and mdl.CrudKitSettings.search_fields and mdl.TYPE_ID == search_type
            ]
        else:
            possible_searches = [
                mdl
                for mdl in get_model_types().values()
                if hasattr(mdl, "CrudKitSettings") and mdl.CrudKitSettings.search_fields
            ]

        for mdl in possible_searches:
            if not has_model_permission(request.user, mdl, "view"):
                continue
            serializer_cls = get_serializer(mdl, depth=0, fields=["id", "label", "object_images"])
            allowed = get_authorized_queryset(request.user, mdl.objects.all(), "view")
            qs = mdl.objects.none()
            for field in mdl.CrudKitSettings.search_fields:
                qs = qs | allowed.filter(**{f"{field}__icontains": query.strip()})
            if "deleted" in [field.name for field in mdl._meta.fields]:
                qs = qs.filter(deleted=False)
            results += [serializer_cls(obj).data for obj in qs[0 : (20 if len(possible_searches) == 1 else 5)]]

        return Response({"results": results})


class WidgetsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]  # TODO add permissions

    def list(self, request):
        """
        Return a list of widgets for the dashboard based on the user's permissions.
        The widgets are imported dynamically from settings.CRUDKIT_DASHBOARD_WIDGETS.

        The setting should be a string pointing to a function that takes a user as parameter
        and returns a list of widget instances.
        """
        from django.conf import settings
        from django.utils.module_loading import import_string

        # Check if the dashboard widgets setting is configured
        if not hasattr(settings, "CRUDKIT_DASHBOARD_WIDGETS"):
            return Response([])

        # Import the widgets function dynamically
        try:
            widgets_function = import_string(settings.CRUDKIT_DASHBOARD_WIDGETS)
            # Get the widgets for the current user
            widgets = widgets_function(request.user)
            # Serialize the widgets
            serialized_widgets = [widget.json() for widget in widgets]
            return Response(serialized_widgets)
        except (ImportError, AttributeError) as e:
            # Log the error but return an empty list to avoid breaking the frontend
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error loading dashboard widgets: {str(e)}")
            return Response([])
