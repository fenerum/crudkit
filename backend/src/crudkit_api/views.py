import copy
import re

from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.core.exceptions import ValidationError
from django.db import connection, models, reset_queries, transaction
from django.db.models import ProtectedError
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from crudkit.audit import audit
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
from crudkit_api.services import (
    get_history,
    perform_action,
    restore_object,
    revert_change_set,
    search_filter,
    search_objects,
)

# The Client-Id the bundled SPA sends; its JWT requests count as "ui". Any
# client can send it: `source` is attribution for the History tab, never an
# authorization input. Only "agent" changes behaviour (agents don't trigger
# agents), and no request can claim it.
SPA_CLIENT_ID = "CrudKitAPIClient"
CHANGE_SET_HEADER = "X-CrudKit-Change-Set"


class AuditedViewMixin:
    """Attribute ChangeLog entries written by this view to the caller (see
    crudkit.audit), and tell the client which change set its write made."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        client_id = request.headers.get("Client-Id", "")
        if isinstance(request.successful_authenticator, SessionAuthentication) or client_id == SPA_CLIENT_ID:
            source, client = "ui", ""
        else:
            source, client = "api", client_id
        self._audit = audit(source, client=client, user=request.user)
        self._audit.__enter__()

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        scope = getattr(self, "_audit", None)
        if scope and request.method not in SAFE_METHODS and scope.context.logged and response.status_code < 400:
            response[CHANGE_SET_HEADER] = str(scope.context.change_set)
        return response

    def dispatch(self, request, *args, **kwargs):
        # DRF skips finalize_response when it re-raises an unhandled exception,
        # so the context is left here, where it always runs.
        try:
            return super().dispatch(request, *args, **kwargs)
        finally:
            if scope := getattr(self, "_audit", None):
                del self._audit
                scope.__exit__(None, None, None)


class GenericViewSet(AuditedViewMixin, viewsets.ModelViewSet):
    permission_classes = [CrudKitModelPermissions]

    def get_queryset(self):
        queryset = super().get_queryset()
        action = get_permission_action(self.request.method, getattr(self, "action", None))
        return get_authorized_queryset(self.request.user, queryset, action)

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        if (
            hasattr(self.queryset.model, "deleted")
            and not self.request.GET.get("deleted", False)
            and self.action not in ("history", "restore")
        ):
            queryset = queryset.filter(deleted=False)
        search = self.request.GET.get("_q", False)
        if search:
            queryset = queryset.filter(search_filter(self.queryset.model, search))
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
        ChangeLog.objects.create_from_objects(instance, None, user=self.request.user)
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

    def _serialize_rows(self, rows):
        # One serializer for all rows: building fields per row allocates ~400 KB per object.
        serializer = self.get_serializer_class()(context={"request": self.request})
        data = []
        for obj in rows:
            # MoneyFieldSerializer reads the current object to find the right currency
            self.request._current_object_for_serialization = obj
            serializer.instance = obj
            data.append(serializer.to_representation(obj))
        return data

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
            # A GenericRelation also installs a reverse descriptor of the same
            # name on its target, so on FeedItem and ExternalObject the base
            # class' feeditem_set/externalobject_set are shadowed and
            # prefetching them by name walks the relation backwards. Nothing in
            # GenericSerializer renders a generic relation anyway.
            and not isinstance(f, GenericRelation)
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
                if queryset.model is not User
                else []
            ),
            *prefetchable_fields,
        )

        # Always use pagination when it's enabled in settings
        page = self.paginate_queryset(queryset)
        if page is not None:
            data = self._serialize_rows(page)
            response = self.get_paginated_response(data)
            response.headers["X-Query-Count"] = str(len(connection.queries))
            return response

        # Fallback for when pagination is disabled
        data = self._serialize_rows(queryset)

        return Response(data, headers={"X-Query-Count": len(connection.queries)})

    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @action(["POST"], detail=True, url_path="merge")
    def merge(self, request, pk=None):
        post_data = request.data
        try:
            with transaction.atomic():
                to_stay_obj = get_object_or_404(self.filter_queryset(self.get_queryset()), pk=post_data.pop("id", pk))
                self.check_object_permissions(request, to_stay_obj)
                other_objects = self.get_queryset().filter(id__in=post_data.pop("merge")).exclude(id=to_stay_obj.id)

                if not all([x.TYPE_ID == to_stay_obj.TYPE_ID for x in other_objects]):
                    raise Exception(
                        "Cannot merge objects of different types %s"
                        % ([x.TYPE_ID for x in other_objects] + [to_stay_obj.TYPE_ID])
                    )
                if not other_objects:
                    raise Exception("No objects to merge")

                merge_fields = post_data
                objects_by_id = {obj.id: obj for obj in [to_stay_obj, *other_objects]}

                before = copy.copy(to_stay_obj)
                for field, value in merge_fields.items():
                    setattr(to_stay_obj, field, getattr(objects_by_id[value], field))
                to_stay_obj.updated_by = request.user
                # The same model validation a PATCH gets (e.g. who an agent may run as).
                to_stay_obj.clean()
                to_stay_obj.save()
                ChangeLog.objects.create_from_objects(
                    before,
                    to_stay_obj,
                    user=request.user,
                    action=ChangeLog.Action.MERGE,
                    label=f"Merged {len(other_objects)} record(s) into {to_stay_obj}",
                )

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
        response = perform_action(instance, action_name, request.user, request=self.request)
        if isinstance(response, HttpResponseRedirect):
            return Response({"redirect": response.url})
        if isinstance(response, models.Model):
            return Response({"redirect": response.id})
        return response

    @action(detail=True)
    def history(self, request, pk=None):
        # The change log keeps old values and who changed what, so it needs its
        # own permission on top of seeing the record.
        if not has_model_permission(request.user, ChangeLog, "view"):
            raise PermissionDenied("You may not view change history.")
        return Response(get_history(self.get_object()))

    @action(["POST"], detail=True)
    def restore(self, request, pk=None):
        instance = self.get_object()
        try:
            restore_object(instance, request.user)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        return Response(self.get_serializer(instance).data)

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
        return Response(build_model_metadata(self.queryset.model, request.user))


class ChangeSetRevertView(AuditedViewMixin, APIView):
    """POST {force} to undo a change set; 409 with the conflicts if records
    have changed since, unless forced."""

    permission_classes = [IsAuthenticated]

    def post(self, request, change_set):
        if not ChangeLog.objects.filter(change_set=change_set).exists():
            raise NotFound("Unknown change set")
        try:
            result = revert_change_set(change_set, request.user, force=bool(request.data.get("force")))
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        return Response(result, status=409 if "conflicts" in result else 200)


CRM_TYPE_REGEX = re.compile(r"[A-Z]{3}")


class SearchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        query = request.GET.get("q")
        if not query:
            return Response({"results": []})

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

        # One more than the palette shows per type, so it knows when to offer "Show all".
        results = search_objects(request.user, query, possible_searches, 21 if len(possible_searches) == 1 else 6)
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
