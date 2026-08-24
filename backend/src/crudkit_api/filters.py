from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models.functions import Lower
from rest_framework import filters
from rest_framework.exceptions import NotFound, ValidationError

from crudkit.authorization import get_authorized_queryset
from crudkit.models import View, parse_ck_id
from crudkit.utils import get_model_types, resolve_variable_value


class BasicFilter(filters.BaseFilterBackend):
    """
    allowed_filters = {
        'query_field_name': 'lookup'
    }
    """

    def filter_queryset(self, request, queryset, view):
        # Start with view-based filtering
        order_by = None
        group_by = None
        pivot_by = None

        if "_view" in request.query_params:
            view_obj = (
                get_authorized_queryset(request.user, View.objects.all(), "view")
                .filter(pk=request.query_params["_view"])
                .first()
            )
            if view_obj is None:
                raise NotFound("Saved view not found.")
            model_type_id = getattr(queryset.model, "TYPE_ID", None)
            if model_type_id and view_obj.model != model_type_id:
                raise ValidationError("Saved view does not match this model.")
            if view_obj.filters:
                queryset = view_obj.filter(queryset, request=request)

            # Store view's ordering fields for later use
            if view_obj.order_by:
                order_by = view_obj.order_by
            if view_obj.group_by:
                group_by = view_obj.group_by
            if view_obj.pivot_by:
                pivot_by = view_obj.pivot_by
        # Handle standard field filters
        for field in queryset.model._meta.get_fields():
            if field.name in request.query_params:
                value = resolve_variable_value(request, request.query_params[field.name])
                if type(field) is GenericForeignKey:
                    # Here we use the composite ID field to get the model and ID from the same field
                    field: GenericForeignKey = field
                    model_type, pk = parse_ck_id(value)
                    queryset = queryset.filter(
                        **{
                            field.ct_field: ContentType.objects.get_for_model(get_model_types()[model_type]).pk,
                            field.fk_field: pk,
                        }
                    )
                else:
                    queryset = queryset.filter(**{field.name: value})
            elif f"{field.name}__isnull" in request.query_params:
                value = request.query_params[f"{field.name}__isnull"] == "True"
                queryset = queryset.filter(**{f"{field.name}__isnull": value})

        # Get the _order_by parameter if provided
        api_order_by = request.query_params.get("_order_by", None)

        # Build ordering fields list based on group_by, pivot_by and order_by from view, plus api_order_by
        order_fields = []

        # Add fields in hierarchical order: pivot_by, group_by, then order_by
        if pivot_by:
            order_fields.append(pivot_by)
        if group_by:
            order_fields.append(group_by)

        # Add order_by fields - API parameter takes precedence over view's order_by
        if api_order_by:
            # API parameter overrides view's order_by
            for field in api_order_by.split(","):
                field = field.strip()
                if field and field not in order_fields:
                    order_fields.append(field)
        elif order_by:
            # Use view's order_by if no API parameter
            for field in order_by.split(","):
                field = field.strip()
                if field and field not in order_fields:
                    order_fields.append(field)

        # Apply case-insensitive ordering if available
        if order_fields:
            # Process order fields to make text fields case-insensitive
            case_insensitive_order_fields = []
            for field in order_fields:
                # Handle descending ordering (fields starting with '-')
                desc = field.startswith("-")
                field_name = field[1:] if desc else field

                # Check if field is a string-based field that needs case-insensitive ordering
                # Common text field names - apply Lower() to these
                text_field_names = ["name", "title", "label", "subject", "description", "text"]
                if field_name.lower() in text_field_names:
                    # Use Lower() for case-insensitive ordering
                    if desc:
                        case_insensitive_order_fields.append(Lower(field_name).desc())
                    else:
                        case_insensitive_order_fields.append(Lower(field_name))
                else:
                    # For non-text fields, keep original ordering
                    case_insensitive_order_fields.append(field)

            # Apply the order_by with case-insensitive fields
            queryset = queryset.order_by(*case_insensitive_order_fields)

        return queryset
