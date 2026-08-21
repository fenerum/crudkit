import re

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.fields.files import ImageFieldFile
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.phonenumber import PhoneNumber

from crudkit.fields import DEFAULT_CURRENCY, CurrencyField, ModelField
from crudkit.utils import get_model_types, get_system_user


def get_ck_id(type_id, pk):
    return f"{type_id}{pk}"


def parse_ck_id(ck_id: str) -> tuple[str, int]:
    return ck_id[0:3], int(ck_id[3:])


ck_id_regex = re.compile("^[A-Z]{3}[0-9]+$")


class CrudKitIDField(models.BigAutoField):
    # def get_internal_type(self):
    #     return "CKIDField"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        # Handle case where model doesn't have TYPE_ID defined (e.g., in migrations)
        if not hasattr(self.model, "TYPE_ID") or self.model.TYPE_ID is None:
            return value
        return get_ck_id(self.model.TYPE_ID, value)

    def to_python(self, value):
        if isinstance(value, str) and ck_id_regex.match(value):  # TODO: Consider regex
            return value

        if value is None:
            return value

        return get_ck_id(self.model.TYPE_ID, super().to_python(value))

    def get_prep_value(self, value):
        if hasattr(value, "pk"):
            # Model instance, e.g. from a FK default callable returning an
            # object; its pk is either a CK-ID string or a raw int.
            value = value.pk
        if type(value) is int:
            return value
        if value == "":
            return None
        if type(value) is str and value is not None:
            type_id, pk = parse_ck_id(value)
        else:
            pk = value
        return super().get_prep_value(pk)

    def get_db_prep_value(self, value, connection, prepared=False):
        if hasattr(value, "pk"):
            value = value.pk
        if type(value) is int:
            return super().get_prep_value(value)
        if value == "":
            return super().get_db_prep_value(None, connection, prepared)
        if value is not None:
            type_id, pk = parse_ck_id(value)
            return super().get_db_prep_value(pk, connection, prepared)
        return super().get_db_prep_value(value, connection, prepared)


class CrudKitPositiveIntegerField(models.PositiveIntegerField):
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        # Handle case where model doesn't have TYPE_ID defined (e.g., in migrations)
        if not hasattr(self.model, "TYPE_ID") or self.model.TYPE_ID is None:
            return value

        # Return raw integer value - formatting happens in serializer
        return value

    def to_python(self, value):
        if isinstance(value, str) and ck_id_regex.match(value):  # TODO: Consider regex
            return value

        if value is None:
            return value

        return get_ck_id(self.model.TYPE_ID, super().to_python(value))

    def get_prep_value(self, value):
        if hasattr(value, "pk"):
            # Model instance, e.g. from a FK default callable returning an
            # object; its pk is either a CK-ID string or a raw int.
            value = value.pk
        if type(value) is int:
            return value
        if value == "":
            return None
        elif value is not None and ck_id_regex.match(value):
            type_id, pk = parse_ck_id(value)
        else:
            pk = value
        return super().get_prep_value(pk)

    def get_db_prep_value(self, value, connection, prepared=False):
        if hasattr(value, "pk"):
            value = value.pk
        if type(value) is int:
            return super().get_prep_value(value)
        if value == "":
            return super().get_db_prep_value(None, connection, prepared)
        elif value is not None and ck_id_regex.match(value):
            type_id, pk = parse_ck_id(value)
            return super().get_db_prep_value(pk, connection, prepared)
        else:
            return super().get_db_prep_value(value, connection, prepared)


class WYSIWYGEditorField(models.TextField):
    pass  # Just for the frontend to know that this field should be rendered with a WYSIWYG editor


class EmailWYSIWYGEditorField(WYSIWYGEditorField):
    pass  # Specialized WYSIWYG editor for email composition with max-height


class BaseCrudKitManager(models.Manager):
    def update_or_create_external(self, system_name, system_id, defaults=None, create_defaults=None, **kwargs):
        """
        Look up an object with the system_name and system_id updating one with defaults.
        if it doesn't exist, lookup by kwargs otherwise create a new one.
        Return a tuple (object, created), where created is a boolean
        specifying whether an object was created.

        TODO: Changelog indicating that the object was updated from an external source
        """
        created = False
        try:
            ext = ExternalObject.objects.get(
                system_name=system_name,
                system_id=system_id,
                related_content_type=ContentType.objects.get_for_model(self.model),
            )
            # Update defaults
            if defaults:
                self.model.objects.filter(pk=ext.related_object.pk).update(**defaults)
                # .update() doesnt trigger signals, so we will do it manually
                ext.related_object.refresh_from_db()
                post_save.send(type(ext.related_object), instance=ext.related_object, created=True)
        except ExternalObject.DoesNotExist:
            if kwargs:
                obj, created = self.update_or_create(defaults=defaults, create_defaults=create_defaults, **kwargs)
            else:
                obj = self.create(**kwargs, **create_defaults or defaults)
                created = True

            system = get_system_user()
            create_kwargs = {"created_by": system, "updated_by": system}
            ext = ExternalObject.objects.create(
                system_name=system_name,
                system_id=system_id,
                related_object=obj,
                **create_kwargs,
            )
        return ext.related_object, created

    def get_external(self, system_name, system_id, **kwargs):
        try:
            return self.get(
                pk=ExternalObject.objects.get(
                    system_name=system_name,
                    system_id=system_id,
                    related_content_type=ContentType.objects.get_for_model(self.model),
                ).related_object.pk,
                **kwargs,
            )
        except ExternalObject.DoesNotExist as e:
            raise self.model.DoesNotExist from e


class BaseCrudKitModel(models.Model):
    id = CrudKitIDField(editable=False, primary_key=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        editable=False,
        related_name="%(class)s_created_by_set",
    )
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        editable=False,
        related_name="%(class)s_updated_by_set",
    )
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    deleted = models.BooleanField(default=False, editable=False)
    merged_into = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        editable=False,
        related_name="%(class)s_merged_set",
    )

    feeditem_set = GenericRelation(
        "crudkit.FeedItem",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
        related_query_name="%(class)s_set",
    )
    externalobject_set = GenericRelation(
        "crudkit.ExternalObject",
        content_type_field="related_content_type",
        object_id_field="related_object_id",
        related_query_name="%(class)s_set",
    )

    TYPE_ID = None  # TODO: should we have models without?

    objects = BaseCrudKitManager()

    def __str__(self):
        return self.id or "[Unsaved instance]"

    def get_user_id(self):
        # DEPRECATED, use `crm_id`
        return self.pk

    @property
    def _actions(self):
        return {
            name: getattr(self, name)
            for name, func in self.__class__.__dict__.items()
            if getattr(func, "_crm_action", False)
        }

    def soft_delete(self, merged_into=None):
        if merged_into:
            self.merged_into = merged_into
        self.deleted = True
        self.save(
            update_fields=["deleted", "updated_at"] if not merged_into else ["deleted", "merged_into", "updated_at"]
        )

    @property
    def crm_id(self):
        return self.get_user_id()

    def __init__(self, *args, **kwargs):
        if self.TYPE_ID is None:
            raise Exception("Please define TYPE_ID on the BaseCrudKitModel")
        super().__init__(*args, **kwargs)

    @classmethod
    def get_ai_fields(cls) -> list:
        return [f for f in cls._meta.get_fields() if getattr(f, "ai_field", False)]

    def get_ai_context(self) -> str:
        parts = []
        skip = {"deleted", "merged_into", "id", "created_by", "updated_by"}
        for field in self._meta.get_fields():
            if not field.concrete or field.name in skip:
                continue
            if getattr(field, "ai_field", False):
                continue
            if isinstance(field, (models.ImageField, models.FileField)):
                continue
            value = getattr(self, field.name, None)
            if value is not None:
                parts.append(f"{field.verbose_name}: {value}")
        return "\n".join(parts)

    def get_fields(self):
        return [
            {"field": field, "value": getattr(self, field.name) if self.pk else None}
            for field in self._meta.fields
            if field.name
            not in [
                "deleted",
                "merged_into",
            ]
        ]

    def get_object_images(self):
        return []

    @classmethod
    def from_query_params(cls, params, kwargs=None):
        instance = cls(**(kwargs if kwargs else {}))
        for field in instance._meta.fields:
            if field.name in params and field.name in cls.CrudKitSettings.allowed_prefills:
                if field.__class__ is models.ForeignKey:
                    setattr(instance, field.name, field.related_model.objects.get(pk=params[field.name]))
                else:
                    setattr(instance, field.name, params[field.name])
        return instance

    def delete_and_merge_with(self, other_object):
        """
        This functions moves any related object to the `other_object`. It should not
        move field content, as this is handled by the merge view where the user
        may pick how the fields are merged
        """
        self.externalobject_set.all().update(related_object_id=other_object.pk)
        FeedItem.objects.filter(
            related_content_type=ContentType.objects.get_for_model(self.__class__),
            related_object_id=self.pk,
        ).update(related_object_id=other_object.pk)
        FeedItem.objects.filter(
            parent_content_type=ContentType.objects.get_for_model(self.__class__),
            parent_object_id=self.pk,
        ).update(parent_object_id=other_object.pk)

        # Update objects merged into the current object to point to the new object, to empty any relations
        self.__class__.objects.filter(merged_into=self).update(merged_into=other_object)

        from django.contrib.admin.utils import NestedObjects
        from django.db import DEFAULT_DB_ALIAS

        collector = NestedObjects(using=DEFAULT_DB_ALIAS)
        collector.collect([self])
        related_objects = collector.nested()
        if len(related_objects) != 1:
            raise ValidationError(
                "Cascading object deletes not handled by delete_and_merge_with: %s" % related_objects,
                params=related_objects,
            )
        self.soft_delete(merged_into=other_object)

    class CrudKitSettings:
        allowed_prefills = []
        search_fields = []
        ai_trigger_children = []
        # Playbook prompt for the per-object AI assistant. Empty → generic
        # fallback prompt is used. Subclasses override to teach the assistant
        # how to think about this model (e.g. MEDDIC checks for Opportunity).
        assistant_prompt = ""
        # Extra pydantic-ai tool callables to register on the assistant for
        # this model. Lets the CRM (or any consumer) plug in model-specific
        # capabilities without touching the framework app.
        assistant_tools = []

    class Meta:
        abstract = True
        ordering = ["id"]


class PrettyJSONEncoder(DjangoJSONEncoder):
    def __init__(self, *args, indent, sort_keys, **kwargs):
        super().__init__(*args, indent=2, sort_keys=True, **kwargs)

    def default(self, obj):
        if isinstance(obj, PhoneNumber):
            return obj.as_e164
        return super().default(obj)


class Layout(BaseCrudKitModel):
    TYPE_ID = "LAY"

    model = ModelField()
    fields = models.JSONField(
        null=True,
        blank=True,
        help_text=("Format: [field1, field2, ...] OR left/right: [ [field1, field2, ...], [field3, field4, ...] ]"),
        encoder=PrettyJSONEncoder,
    )
    inlines = models.JSONField(
        null=True,
        blank=True,
        help_text=("Format: [ [Model, [field1, field2, field...] ]"),
        encoder=PrettyJSONEncoder,
    )

    def __str__(self):
        return f"{self.get_user_id()}: {self.model}"

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        allowed_prefills = ["model", "fields"]

    # Names that the frontend's `generateFieldPairs` always filters out when
    # rendering the default detail view without a saved Layout. Keeping the
    # default initial value in sync with that means a brand-new layout starts
    # out matching what users already see on the detail page.
    DEFAULT_HIDDEN_FIELDS = ("deleted", "merged_into")

    @classmethod
    def from_query_params(cls, params, kwargs=None):
        instance = super().from_query_params(params, kwargs)
        if "model" in params:
            field_names = [
                f.name
                for f in get_model_types()[params["model"]]._meta.fields
                if f.name not in cls.DEFAULT_HIDDEN_FIELDS
            ]
            # Pair fields into rows of 2 — same shape as the frontend's default
            # detail layout (left column / right column) when no Layout exists.
            instance.fields = [field_names[i : i + 2] for i in range(0, len(field_names), 2)]
        return instance


class View(BaseCrudKitModel):
    TYPE_ID = "VIW"

    class ViewLayoutChoices(models.TextChoices):
        LIST = "list"
        KANBAN = "kanban"
        GALLERY = "gallery"
        SWIMLANE = "swimlane"
        CONVERSATION = "conversation"
        QUADRANT = "quadrant"

    model = ModelField()
    layout = models.CharField(
        max_length=128,
        choices=ViewLayoutChoices.choices,
        default=ViewLayoutChoices.LIST,
    )
    name = models.CharField(max_length=128)
    default = models.BooleanField(blank=True, default=False)
    public = models.BooleanField(blank=True, default=True)
    show_in_menu = models.BooleanField(blank=True, default=True)
    show_badge_in_menu = models.BooleanField(
        blank=True,
        default=False,
        help_text=_("This will make every page in the CRM load slower, please use with caution"),
    )
    fields = models.JSONField(help_text=("Format: [field1, field2, field...]"), encoder=PrettyJSONEncoder)
    filters = models.JSONField(
        null=True,
        blank=True,
        help_text=("Format: [[field, comparator, value], [field, comparator, value], ...]"),
        encoder=PrettyJSONEncoder,
    )

    order_by = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="Format: field or -field - you can optionally add multiple with a comma between and not space",
    )
    group_by = models.CharField(max_length=128, blank=True, null=True)
    pivot_by = models.CharField(max_length=128, blank=True, null=True)

    class AggregationTypes(models.TextChoices):
        SUM = "sum"
        COUNT = "len"

    aggregate_by = models.CharField(max_length=128, blank=True, null=True)
    aggregate_type = models.CharField(max_length=3, choices=AggregationTypes.choices, blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.get_user_id()}: {self.model}"

    def clean(self):
        """
        Validate that the model exists and all referenced fields exist on the model.
        """
        model_types = get_model_types()

        # Validate model exists
        if self.model not in model_types:
            raise ValidationError({"model": _(f"Model '{self.model}' does not exist.")})

        model_class = model_types[self.model]
        model_field_names = [field.name for field in model_class._meta.fields]

        # Validate fields exist
        if self.fields:
            for field_name in self.fields:
                if field_name not in model_field_names:
                    raise ValidationError(
                        {"fields": _(f"Field '{field_name}' does not exist on model '{self.model}'.")}
                    )

        # Validate filter fields exist
        if self.filters:
            for field_spec in self.filters:
                if not field_spec or len(field_spec) < 3:
                    raise ValidationError(
                        {"filters": _("Filter format is invalid. Should be [field, comparator, value]")}
                    )

                field_name = field_spec[0]
                # Skip validating field paths with relationships (field__subfield)
                if "__" not in field_name and field_name not in model_field_names:
                    raise ValidationError(
                        {"filters": _(f"Field '{field_name}' does not exist on model '{self.model}'.")}
                    )

        # Validate order_by fields exist
        if self.order_by:
            for field_name in self.order_by.split(","):
                # Strip the minus sign for descending order
                clean_field_name = field_name.strip("-").strip()
                if clean_field_name not in model_field_names:
                    raise ValidationError(
                        {"order_by": _(f"Field '{clean_field_name}' does not exist on model '{self.model}'.")}
                    )

        # Validate group_by field exists
        if self.group_by and self.group_by not in model_field_names:
            raise ValidationError({"group_by": _(f"Field '{self.group_by}' does not exist on model '{self.model}'.")})

        # Validate pivot_by field exists
        if self.pivot_by and self.pivot_by not in model_field_names:
            raise ValidationError({"pivot_by": _(f"Field '{self.pivot_by}' does not exist on model '{self.model}'.")})

        # Validate aggregate_by field exists
        if self.aggregate_by and self.aggregate_by not in model_field_names:
            raise ValidationError(
                {"aggregate_by": _(f"Field '{self.aggregate_by}' does not exist on model '{self.model}'.")}
            )

        # Validate aggregate_type is set if aggregate_by is set
        if self.aggregate_by and not self.aggregate_type:
            raise ValidationError({"aggregate_type": _("Aggregate type must be set when aggregate_by is specified.")})

        # Validate aggregate_type is not set if aggregate_by is not set
        if self.aggregate_type and not self.aggregate_by:
            raise ValidationError(
                {"aggregate_type": _("Aggregate type should not be set when aggregate_by is not specified.")}
            )

        # Validate quadrant view has at least 2 fields for X and Y axes
        if self.layout == self.ViewLayoutChoices.QUADRANT:
            if not self.fields or len(self.fields) < 2:
                raise ValidationError(
                    {"fields": _("Quadrant views require at least 2 fields (first=X-axis, second=Y-axis).")}
                )

    def filter(self, qs, request=None):
        for field, comparator, value in self.filters or []:
            # Resolve variables like ${user} if a request is provided
            if request and isinstance(value, str):
                from crudkit.utils import resolve_variable_value

                value = resolve_variable_value(request, value)

            if comparator == "=":
                qs = qs.filter(**{field: value})
            elif comparator == "!=":
                qs = qs.exclude(**{field: value})
            elif comparator == ">":
                qs = qs.filter(**{f"{field}__gt": value})
            elif comparator == ">=":
                qs = qs.filter(**{f"{field}__gte": value})
            elif comparator == "<":
                qs = qs.filter(**{f"{field}__lt": value})
            elif comparator == "<=":
                qs = qs.filter(**{f"{field}__lte": value})
            else:
                raise ValueError("Unknown comparator in saved view %s" % comparator)
        return qs

    def get_model(self):
        return get_model_types()[self.model]

    def get_count(self, request=None):
        return self.filter(self.get_model().objects.all(), request=request).count()

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        allowed_prefills = ["model", "fields"]

    @classmethod
    def from_query_params(cls, params, kwargs=None):
        instance = super().from_query_params(params, kwargs)
        if "model" in params and not instance.fields:
            instance.fields = [f.name for f in get_model_types()[params["model"]]._meta.fields]
        return instance


class Workspace(BaseCrudKitModel):
    TYPE_ID = "WSP"

    name = models.CharField(max_length=128)
    icon = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text=_("Icon name shown in the workspace switcher"),
    )
    public = models.BooleanField(blank=True, default=True)
    views = models.JSONField(
        blank=True,
        default=list,
        encoder=PrettyJSONEncoder,
        help_text='Format: ["VIW1", "VIW2", ...] — tab order follows the list order',
    )

    class Meta:
        ordering = ["name"]

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if not isinstance(self.views, list):
            raise ValidationError({"views": _('Format: ["VIW1", "VIW2", ...]')})
        for ck_id in self.views:
            if not isinstance(ck_id, str) or not ck_id_regex.match(ck_id) or ck_id[:3] != View.TYPE_ID:
                raise ValidationError({"views": _(f"'{ck_id}' is not a View id.")})
            if not View.objects.filter(pk=ck_id).exists():
                raise ValidationError({"views": _(f"View '{ck_id}' does not exist.")})


class FeedItem(BaseCrudKitModel):
    TYPE_ID = "FEI"

    parent_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        editable=False,
        related_query_name="parent_content_type",
    )
    parent_object_id = CrudKitPositiveIntegerField(editable=False)
    parent_object = GenericForeignKey("parent_content_type", "parent_object_id")

    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        editable=False,
        related_name="related_content_type",
        null=True,
    )
    related_object_id = CrudKitPositiveIntegerField(editable=False, null=True)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    body = WYSIWYGEditorField(null=True, blank=True)

    pinned = models.BooleanField(default=False, blank=True)

    def get_content(self):
        if self.related_content_type and self.related_content_type.model == "email" and self.related_object:
            return self.related_object.get_content()
        return {
            "text": self.body,
            "html": self.body,
        }

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        allowed_prefills = ["parent_content_type", "parent_object"]

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["parent_content_type", "parent_object_id"]),
            models.Index(fields=["related_content_type", "related_object_id"]),
        ]


class ExternalObject(BaseCrudKitModel):
    TYPE_ID = "EXT"

    system_name = models.CharField(max_length=128)
    system_id = models.CharField(max_length=128)
    related_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, editable=False, null=True)
    related_object_id = CrudKitPositiveIntegerField(editable=False, null=True)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    class CrudKitSettings:
        search_fields = ["system_id"]

    class Meta:
        unique_together = ["system_name", "system_id", "related_content_type"]


class ChangeLogManager(models.Manager):
    def create_from_objects(self, old, new):
        if type(new) is ChangeLog:
            raise Exception("Cannot change a ChangeLog object")
        field_changes = {}
        if new:
            for field in new._meta.fields:
                if field.name not in [
                    "id",
                    "created_at",
                    "updated_at",
                    "created_by",
                    "updated_by",
                ]:
                    # Get values
                    old_value = None
                    if old is not None:
                        old_value = old.__dict__.get(field.get_attname())
                    new_value = new.__dict__.get(field.get_attname())
                    # Convert to serializable
                    if type(field) in [models.FileField, models.ImageField]:
                        if old_value and isinstance(old_value, ImageFieldFile):
                            old_value = old_value.url
                        if new_value and isinstance(new_value, ImageFieldFile):
                            new_value = new_value.url
                        else:  # Catch special case where the image is not saved
                            new_value = None
                    # Check if changed
                    change = [old_value, new_value]
                    if change[0] != change[1]:
                        field_changes[field.name] = change
        type_id, pk = parse_ck_id(new.pk if new else old.pk)
        self.model.objects.create(
            related_object_id=pk,
            related_content_type=ContentType.objects.get_for_model(new if new else old),
            field_changes=field_changes,
            created_by=new.updated_by if new else old.created_by,
            updated_by=new.updated_by if new else old.updated_by,
        )


class ChangeLog(BaseCrudKitModel):
    TYPE_ID = "CHG"

    related_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, editable=False, null=True)
    related_object_id = CrudKitPositiveIntegerField(editable=False, null=True)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    field_changes = models.JSONField(
        null=True,
        blank=True,
        help_text=('Format: {"field": ["old_value", "new_value"], "field2": ["old_value", "new_value"], ...}'),
        encoder=PrettyJSONEncoder,
    )

    objects = ChangeLogManager()

    class Meta:
        indexes = [models.Index(fields=["updated_at"])]


class ExchangeRateManager(BaseCrudKitManager):
    def get_rate_for_date(self, currency, date=None):
        """
        Get the exchange rate for a specific currency and date.
        """
        if currency == DEFAULT_CURRENCY:
            return 1

        if not date:
            date = timezone.now().date()

        try:
            rate_obj = (
                self.filter(currency=currency, from_date__lte=date)
                .filter(models.Q(to_date__gte=date) | models.Q(to_date__isnull=True))
                .get()
            )
            return rate_obj.rate
        except self.model.DoesNotExist:
            return None
        except self.model.MultipleObjectsReturned:
            # This shouldn't happen due to validation, but just in case
            rate_obj = (
                self.filter(currency=currency, from_date__lte=date)
                .filter(models.Q(to_date__gte=date) | models.Q(to_date__isnull=True))
                .order_by("-from_date")
                .first()
            )
            return rate_obj.rate if rate_obj else None


class WorkLog(BaseCrudKitModel):
    """
    Model for tracking time spent on any object in the system.
    Uses created_at as the start time, and end_at when tracking is stopped.
    """

    TYPE_ID = "WLG"

    # Generic relation to track time on any object
    related_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, editable=False)
    related_object_id = CrudKitPositiveIntegerField(editable=False)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    # When time tracking ended (null means active)
    end_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When time tracking ended. Null means it's still active.")
    )

    # Optional notes about the time spent
    notes = models.TextField(null=True, blank=True, help_text=_("Notes about the time spent"))

    class Meta:
        verbose_name = _("Work Log")
        verbose_name_plural = _("Work Logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by", "end_at"]),
            models.Index(fields=["related_content_type", "related_object_id"]),
        ]
        unique_together = [("created_by", "end_at")]

    def __str__(self):
        return f"Work log on {self.related_object} from {self.created_at}"

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        allowed_prefills = ["related_content_type", "related_object_id"]
        search_fields = []


class ExchangeRate(BaseCrudKitModel):
    """
    Model for storing currency exchange rates.

    Each record represents an exchange rate from the default currency (base_currency)
    to a target currency for a specific time period.
    """

    TYPE_ID = "EXR"

    objects = ExchangeRateManager()

    # The target currency this rate applies to
    # Settings values must not appear in field kwargs: they would be baked
    # into migrations and drift per-project.
    currency = CurrencyField(help_text=_("The target currency, relative to the configured base currency."))

    # The time period this rate is valid for
    from_date = models.DateField(default=timezone.now)
    to_date = models.DateField(null=True, blank=True, help_text=_("Leave blank for rates that apply indefinitely"))

    # The exchange rate (1 base_currency = X target_currency)
    rate = models.DecimalField(
        max_digits=16,
        decimal_places=8,
        help_text=_("Exchange rate from the base currency to the target currency (1 base = X target)"),
    )

    class Meta:
        verbose_name = _("Exchange Rate")
        verbose_name_plural = _("Exchange Rates")
        ordering = ["-from_date", "currency"]
        # Index for faster lookups
        indexes = [
            models.Index(fields=["currency", "from_date", "to_date"]),
        ]

    def __str__(self):
        to_date_str = f" - {self.to_date}" if self.to_date else " - ongoing"
        return f"1 {DEFAULT_CURRENCY} = {self.rate} {self.currency} ({self.from_date}{to_date_str})"

    def clean(self):
        """
        Validate that there are no overlaps for a currency in terms of from_date and to_date.
        """
        # Set a far future date for "no end date" comparisons
        far_future = timezone.now().date() + timezone.timedelta(days=36500)
        effective_to_date = self.to_date or far_future

        # Check for start date after end date
        if self.to_date and self.from_date > self.to_date:
            raise ValidationError({"to_date": _("End date must be after start date")})

        # Check for overlapping date ranges for the same currency
        overlapping_query = models.Q(
            # Overlapping cases:
            # 1. starts during our range
            models.Q(from_date__gte=self.from_date, from_date__lte=effective_to_date)
            |
            # 2. ends during our range
            models.Q(to_date__gte=self.from_date, to_date__lte=effective_to_date)
            |
            # 3. spans our entire range
            models.Q(from_date__lte=self.from_date, to_date__gte=effective_to_date)
            |
            # 4. our range spans their entire range
            models.Q(from_date__gte=self.from_date, to_date__lte=effective_to_date)
        )

        overlapping_filter = ExchangeRate.objects.filter(currency=self.currency).filter(overlapping_query)

        # If this is an existing instance being updated, exclude self from check
        if self.pk:
            overlapping_filter = overlapping_filter.exclude(pk=self.pk)

        if overlapping_filter.exists():
            raise ValidationError(
                _("This exchange rate overlaps with an existing rate for the same currency: %(existing)s"),
                params={"existing": str(overlapping_filter.first())},
            )

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        allowed_prefills = ["currency", "from_date", "to_date", "rate"]
        search_fields = ["currency"]


class Snippet(BaseCrudKitModel):
    TYPE_ID = "SNP"

    name = models.CharField(max_length=128)
    body = WYSIWYGEditorField(help_text="The snippet content to insert")
    model_types = models.JSONField(
        default=list,
        blank=True,
        help_text='List of model TYPE_IDs this snippet is available for, e.g. ["CAS", "OPP"]. Empty means available everywhere.',
    )

    def __str__(self):
        return self.name

    class CrudKitSettings(BaseCrudKitModel.CrudKitSettings):
        search_fields = ["name"]
