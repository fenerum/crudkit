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
        view_obj = None
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

        return order_queryset(queryset, get_order_fields(view_obj, request.query_params.get("_order_by")))


TEXT_FIELD_NAMES = {"name", "title", "label", "subject", "description", "text"}


def get_order_fields(view_obj, order_by: str | None = None) -> list[str]:
    """pivot_by, group_by, then `order_by` — which overrides the saved view's own order_by."""
    order_fields = []
    if view_obj is not None:
        order_fields += [f for f in (view_obj.pivot_by, view_obj.group_by) if f]
        order_by = order_by or view_obj.order_by
    for field in (order_by or "").split(","):
        field = field.strip()
        if field and field not in order_fields:
            order_fields.append(field)
    return order_fields


def order_queryset(queryset, order_fields: list[str]):
    """Order by `order_fields`, case-insensitively for common text field names."""
    if not order_fields:
        return queryset
    ordering = []
    for field in order_fields:
        desc = field.startswith("-")
        field_name = field.lstrip("-")
        if field_name.lower() in TEXT_FIELD_NAMES:
            ordering.append(Lower(field_name).desc() if desc else Lower(field_name))
        else:
            ordering.append(field)
    return queryset.order_by(*ordering)
