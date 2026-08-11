import mimetypes

from django.core.exceptions import FieldDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from drf_extra_fields.fields import Base64FieldMixin, Base64ImageField
from rest_framework import serializers
from rest_framework.fields import CharField, FileField

from crudkit.fields import DEFAULT_CURRENCY
from crudkit.fields import MoneyField as CrudKitMoneyField
from crudkit.models import CrudKitIDField, CrudKitPositiveIntegerField, get_ck_id, parse_ck_id
from crudkit.profile import get_object_images as crudkit_object_images
from crudkit.utils import get_model_types


class CustomBase64FileField(Base64FieldMixin, FileField):
    """
    A custom file field that supports base64 encoded files.
    Accepts all file types and determines extension from MIME type.
    """

    # Accept basic office files and images
    ALLOWED_TYPES = [
        # Office documents
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        # Images
        "jpg",
        "jpeg",
        "png",
        "gif",
        "bmp",
        "webp",
        # Text
        "txt",
        "csv",
    ]

    def get_file_extension(self, filename, decoded_file):
        # Try to get extension from filename first
        if filename and "." in filename:
            return filename.split(".")[-1].lower()

        # For base64 data URLs, try to extract mime type
        if hasattr(self, "_mime_type") and self._mime_type:
            extension = mimetypes.guess_extension(self._mime_type)
            if extension:
                return extension[1:] if extension.startswith(".") else extension

        # Try to detect from file content
        if decoded_file:
            # Check magic bytes for common formats
            if decoded_file.startswith(b"%PDF"):
                return "pdf"
            elif decoded_file.startswith(b"\xff\xd8\xff"):
                return "jpg"
            elif decoded_file.startswith(b"\x89PNG\r\n\x1a\n"):
                return "png"
            elif decoded_file.startswith(b"GIF8"):
                return "gif"
            elif decoded_file.startswith(b"PK\x03\x04"):
                # Could be zip, docx, xlsx, etc.
                return "zip"

        # Default fallback
        return "bin"

    def to_internal_value(self, data):
        # Extract MIME type from data URL if present
        if isinstance(data, str) and data.startswith("data:"):
            try:
                header, ignored = data.split(",", 1)
                mime_type = header.split(":")[1].split(";")[0]
                self._mime_type = mime_type
            except (ValueError, IndexError):
                self._mime_type = None

        return super().to_internal_value(data)


class CrudKitIDFieldSerializer(CharField):
    """Custom serializer field for CrudKitIDField that uses the actual model's TYPE_ID."""

    def to_representation(self, value):
        if value is None:
            return value

        # Get the actual model instance from the parent serializer
        if hasattr(self.parent, "instance"):
            # Single object or list item
            instance = self.parent.instance
            if instance and hasattr(instance.__class__, "TYPE_ID"):
                # Extract numeric ID from the value
                if isinstance(value, str) and len(value) > 3:
                    numeric_id = value[3:]  # Remove any existing prefix
                else:
                    numeric_id = value
                # Return with the correct TYPE_ID for this model
                return get_ck_id(instance.__class__.TYPE_ID, numeric_id)

        # Fallback to default behavior
        return super().to_representation(value)


class CrudKitPositiveIntegerFieldSerializer(CharField):
    """Custom serializer field for CrudKitPositiveIntegerField that ignores numeric field parameters."""

    def __init__(self, **kwargs):
        # Remove numeric field parameters that CharField doesn't accept
        numeric_params = ["max_value", "min_value"]
        for param in numeric_params:
            kwargs.pop(param, None)
        super().__init__(**kwargs)

    def to_representation(self, value):
        """Format the value with the correct TYPE_ID prefix."""
        if value is None:
            return value

        # If already formatted as a string with prefix, return as-is
        if isinstance(value, str):
            from crudkit.models import ck_id_regex

            if ck_id_regex.match(value):
                return value

        # Convert to int if needed
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                return value

        # Get the model instance from parent serializer
        instance = None
        if hasattr(self.parent, "instance"):
            instance = self.parent.instance

        if not instance:
            return value

        # Check if this field is part of a GenericForeignKey
        model_class = instance.__class__
        field_name = self.field_name

        # Look for GenericForeignKey that uses this field
        content_type_field_name = None
        for private_field in model_class._meta.private_fields:
            if hasattr(private_field, "ct_field") and hasattr(private_field, "fk_field"):
                if private_field.fk_field == field_name:
                    content_type_field_name = private_field.ct_field
                    break

        if content_type_field_name:
            # This is a generic FK field - get the related model's TYPE_ID
            content_type = getattr(instance, content_type_field_name, None)
            if content_type:
                try:
                    related_model = content_type.model_class()
                    if related_model and hasattr(related_model, "TYPE_ID"):
                        return get_ck_id(related_model.TYPE_ID, value)
                except Exception:
                    pass
        else:
            # Regular FK field - use the owner model's TYPE_ID
            if hasattr(model_class, "TYPE_ID"):
                return get_ck_id(model_class.TYPE_ID, value)

        return value


class MoneyFieldSerializer(serializers.Field):
    """
    Custom serializer for MoneyField that returns a dictionary with currency information.

    Representation format:
    {
        "currency": "USD",
        "amount": "100.00",
        "amount_default_currency": "700.00",
        "default_currency": "DKK"
    }
    """

    def __init__(self, **kwargs):
        # Remove DecimalField specific kwargs that are not needed for Field
        # These come from the model field definition
        if "max_digits" in kwargs:
            kwargs.pop("max_digits")
        if "decimal_places" in kwargs:
            kwargs.pop("decimal_places")

        super().__init__(**kwargs)

    def to_representation(self, value):
        # If value is None, return None
        if value is None:
            return None

        # Format amount as string with 2 decimal places
        amount_str = f"{value:.2f}"

        # Default values
        instance = None
        currency = DEFAULT_CURRENCY

        # Find the current object that owns this money field
        if hasattr(self.parent, "instance"):
            # Single object case
            if not isinstance(self.parent.instance, list):
                instance = self.parent.instance
            # List case - try to find the current object
            elif isinstance(self.parent.instance, list) and hasattr(
                self.context["request"], "_current_object_for_serialization"
            ):
                # Get the current object from a context we'll set in the view
                instance = self.context["request"]._current_object_for_serialization

        # If we have an instance, get the appropriate currency
        if instance:
            # Get the field name
            field_name = self.source
            # Find the corresponding currency field
            currency_field_name = "currency"

            # If we have a specific currency field paired with this money field, use that
            if hasattr(instance, f"{field_name}_currency"):
                currency_field_name = f"{field_name}_currency"

            # Get the currency
            currency = getattr(instance, currency_field_name, DEFAULT_CURRENCY)

            # Calculate amount in default currency if it's different
            amount_default_currency = value
            if currency != DEFAULT_CURRENCY and hasattr(instance, "convert_to"):
                default_amount = instance.convert_to(DEFAULT_CURRENCY, amount=value)
                if default_amount is not None:
                    amount_default_currency = default_amount

            # Format default currency amount as string with 2 decimal places
            amount_default_currency_str = f"{amount_default_currency:.2f}"

            return {
                "currency": currency,
                "amount": amount_str,
                "amount_default_currency": amount_default_currency_str,
                "default_currency": DEFAULT_CURRENCY,
            }

        # Fallback case - just return with default currency
        return {
            "currency": DEFAULT_CURRENCY,
            "amount": amount_str,
            "amount_default_currency": amount_str,
            "default_currency": DEFAULT_CURRENCY,
        }

    def to_internal_value(self, data):
        # Handle input as dictionary or direct value
        if isinstance(data, dict) and "amount" in data:
            try:
                return float(data["amount"])
            except (ValueError, TypeError) as e:
                raise serializers.ValidationError("Invalid decimal value for amount") from e

        # Handle direct input (string or number)
        try:
            return float(data)
        except (ValueError, TypeError) as e:
            raise serializers.ValidationError("Invalid decimal value") from e


_serializer_field_mapping = serializers.ModelSerializer.serializer_field_mapping.copy()
_serializer_field_mapping.update(
    {
        # Add custom mappings here
        models.ImageField: Base64ImageField,
        models.FileField: CustomBase64FileField,
        CrudKitPositiveIntegerField: CrudKitPositiveIntegerFieldSerializer,
        CrudKitIDField: CrudKitIDFieldSerializer,
        CrudKitMoneyField: MoneyFieldSerializer,
    }
)


class GenericRelationField(serializers.Field):
    def to_representation(self, value):
        return value.pk

    def to_internal_value(self, data):
        mdl, pk = parse_ck_id(data)
        try:
            return get_model_types()[mdl].objects.get(pk=pk)
        except KeyError as e:
            raise serializers.ValidationError(f"Model {mdl} not found") from e


class GenericSerializer(serializers.ModelSerializer):
    serializer_field_mapping = _serializer_field_mapping

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO: Look up all generic relations dynamically
        # Resolved via _meta: on Django >= 6, class-level access to a
        # GenericForeignKey returns a descriptor without `blank`.
        for gfk_name in ("parent_object", "related_object"):
            if hasattr(self.Meta.model, gfk_name):
                try:
                    gfk = self.Meta.model._meta.get_field(gfk_name)
                except FieldDoesNotExist:
                    continue
                self.fields[gfk_name] = GenericRelationField(required=gfk.blank)

        to_be_removed = []

        # Dynamically show fields
        # Skip field filtering for nested serializers (marked with _is_nested attribute)
        is_nested = getattr(self.__class__, "_is_nested", False)
        if "request" in self.context and not is_nested:
            request = self.context["request"]
            fields = request.GET.get("_fields").split(",") if request.GET.get("_fields") else self.fields
            for field in fields:
                if field not in self.fields:
                    raise Exception(f"Field {field} not found in model serializer {self.__class__.__name__}")
            for field in self.fields:
                if field not in fields:
                    to_be_removed.append(field)

        # hack: remove all password fields

        for field_name in self.fields:
            if field_name.lower().endswith("password"):
                to_be_removed.append(field_name)
        for field_name in set(to_be_removed):
            del self.fields[field_name]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        validated_data["updated_by"] = self.context["request"].user
        instance = super().create(validated_data)

        try:
            # Only run the clean method, not full_clean to avoid field validator issues
            instance.clean()
        except DjangoValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            raise serializers.ValidationError(e.message_dict) from e

        return instance

    def update(self, instance, validated_data):
        instance.updated_by = self.context["request"].user
        instance = super().update(instance, validated_data)

        try:
            # Only run the clean method, not full_clean to avoid field validator issues
            instance.clean()
        except DjangoValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            raise serializers.ValidationError(e.message_dict) from e

        return instance

    label = serializers.SerializerMethodField()

    def get_label(self, obj):
        return obj.__str__() if obj.pk else "[Unsaved object]"

    object_images = serializers.SerializerMethodField(method_name="get_object_images")

    def get_object_images(self, obj):
        if obj.pk:
            images = crudkit_object_images(obj)
            request = self.context.get("request")
            if request and images:
                return [request.build_absolute_uri(img) if img.startswith("/") else img for img in images]
            return images
        return []

    def get_field_names(self, declared_fields, info):
        fields = super().get_field_names(declared_fields, info)
        # Many to many fields currently not supported
        for field in self.Meta.model._meta.many_to_many:
            if field.name in fields:
                fields.remove(field.name)
        return fields

    def build_nested_field(self, field_name, relation_info, nested_depth):
        """
        Create nested fields for forward and reverse relationships.
        """

        if relation_info.to_many:  # Currently not supported
            return super().build_nested_field(field_name, relation_info, nested_depth)

        class NestedSerializer(GenericSerializer):
            _is_nested = True

            class Meta:
                model = relation_info.related_model
                depth = nested_depth - 1
                fields = "__all__"

        class RelatedField(serializers.Field):
            def to_representation(self, value):
                return NestedSerializer(value, context=self.context).data

            def to_internal_value(self, data):
                if data is not None:
                    try:
                        # if issubclass(relation_info.related_model, BaseCrudKitModel):
                        # mdl, pk = parse_ck_id(data)
                        # relation_info.related_model.objects.get(id=pk)
                        return relation_info.related_model.objects.get(id=data)
                    except relation_info.related_model.DoesNotExist:
                        pass

        model_fields = {field.name: field for field in self.Meta.model._meta.fields}
        field = model_fields[field_name]
        kwargs = {"required": not field.blank, "allow_null": field.null}
        if field.editable is False:
            if "required" in kwargs:
                del kwargs["required"]
            kwargs["read_only"] = True
        return RelatedField, kwargs


def get_serializer(mdl, depth=1, fields="__all__"):
    return type(
        "%sSerializer" % mdl.__name__,
        (GenericSerializer,),
        {"Meta": type("Meta", (object,), {"model": mdl, "fields": fields, "depth": depth})},
    )
