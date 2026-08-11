"""Management command to backfill AI fields on any CrudKit model."""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from crudkit.fields import AICategoryField, AISummaryField
from crudkit.models import BaseCrudKitModel
from crudkit.tasks import process_ai_fields


class Command(BaseCommand):
    help = "Backfill AI fields for a given model. Example: backfill_ai_fields --model crm.Case"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            required=True,
            help="app_label.ModelName (e.g. crm.Case)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of tasks to dispatch per batch (default 50)",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run synchronously instead of dispatching Celery tasks",
        )

    def handle(self, *args, **options):
        model_path = options["model"]
        batch_size = options["batch_size"]
        sync = options["sync"]

        try:
            app_label, model_name = model_path.split(".")
        except ValueError:
            raise CommandError("--model must be in app_label.ModelName format")

        try:
            model_cls = apps.get_model(app_label, model_name)
        except LookupError:
            raise CommandError(f"Model {model_path} not found")

        if not issubclass(model_cls, BaseCrudKitModel):
            raise CommandError(f"{model_path} is not a BaseCrudKitModel")

        ai_fields = model_cls.get_ai_fields()
        if not ai_fields:
            raise CommandError(f"{model_path} has no AI fields")

        self.stdout.write(f"AI fields: {[f.name for f in ai_fields]}")

        # Build filter: any AI field that is empty/null
        empty_q = Q()
        for field in ai_fields:
            if isinstance(field, (AISummaryField, AICategoryField)):
                empty_q |= Q(**{field.name: None}) | Q(**{field.name: ""})
            else:
                empty_q |= Q(**{field.name: None})

        qs = model_cls.objects.filter(empty_q, deleted=False)
        total = qs.count()
        self.stdout.write(f"Found {total} instances with empty AI fields")

        dispatched = 0
        for pk in qs.values_list("pk", flat=True).iterator(chunk_size=batch_size):
            if sync:
                process_ai_fields(app_label, model_name, pk)
            else:
                process_ai_fields.delay(app_label, model_name, pk)
            dispatched += 1
            if dispatched % batch_size == 0:
                self.stdout.write(f"  dispatched {dispatched}/{total}")

        self.stdout.write(self.style.SUCCESS(f"Done — dispatched {dispatched} tasks"))
