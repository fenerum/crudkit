"""Unit tests for crudkit_api.metadata."""

import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from crudkit_api.metadata import (
    FK_CHOICES_LIMIT,
    _coerce_current_value,
    build_instance_metadata,
    build_model_metadata,
)
from tests.testapp.models import Customer, Ticket, Topic


class CoerceCurrentValueTests(TestCase):
    """`_coerce_current_value` must hand pydantic-ai only JSON-safe primitives,
    since the LLM-facing tool result is serialised by pydantic_core."""

    def test_primitives_pass_through(self):
        for v in (None, "x", 1, 1.5, True, False):
            self.assertEqual(_coerce_current_value(v), v)

    def test_decimal_stringified(self):
        self.assertEqual(_coerce_current_value(Decimal("1.50")), "1.50")

    def test_datetime_isoformat(self):
        d = datetime(2026, 5, 18, 12, 30, tzinfo=UTC)
        self.assertEqual(_coerce_current_value(d), d.isoformat())

    def test_date_isoformat(self):
        self.assertEqual(_coerce_current_value(date(2026, 5, 18)), "2026-05-18")

    def test_time_isoformat(self):
        self.assertEqual(_coerce_current_value(time(9, 0)), "09:00:00")

    def test_timedelta_stringified(self):
        self.assertEqual(_coerce_current_value(timedelta(seconds=5)), "0:00:05")

    def test_uuid_stringified(self):
        u = UUID("12345678-1234-5678-1234-567812345678")
        self.assertEqual(_coerce_current_value(u), str(u))

    def test_list_recurses(self):
        self.assertEqual(
            _coerce_current_value([Decimal("1.5"), date(2026, 1, 1)]),
            ["1.5", "2026-01-01"],
        )

    def test_dict_recurses_with_string_keys(self):
        self.assertEqual(
            _coerce_current_value({1: Decimal(2), "x": date(2026, 1, 1)}),
            {"1": "2", "x": "2026-01-01"},
        )

    def test_unknown_type_falls_back_to_str(self):
        """The whole reason this exists: django_countries.Country and other
        unknown types must not crash pydantic-ai."""

        class Country:
            def __str__(self):
                return "DK"

        self.assertEqual(_coerce_current_value(Country()), "DK")


class BuildModelMetadataTests(TestCase):
    def test_returns_model_level_shape(self):
        md = build_model_metadata(Ticket)
        self.assertEqual(md["type"], Ticket.TYPE_ID)
        self.assertEqual(md["verbose_name"], Ticket._meta.verbose_name)
        self.assertIn("fields", md)
        self.assertIn("relations", md)
        self.assertIn("actions", md)

    def test_includes_each_concrete_field(self):
        md = build_model_metadata(Ticket)
        field_names = {f.name for f in Ticket._meta.fields}
        self.assertEqual(set(md["fields"].keys()), field_names)

    def test_fk_field_metadata(self):
        md = build_model_metadata(Ticket)
        customer_meta = md["fields"]["customer"]
        self.assertEqual(customer_meta["related_model"], "Customer")
        self.assertEqual(customer_meta["related_model_type"], "CUS")

    def test_choices_exposed_on_choice_fields(self):
        md = build_model_metadata(Customer)
        self.assertEqual(md["fields"]["status"]["choices"], tuple(Customer.StatusChoices.choices))

    def test_actions_list_uses_action_keys(self):
        md = build_model_metadata(Customer)
        action_names = [a["action"] for a in md["actions"]]
        self.assertEqual(action_names, list(Customer()._actions.keys()))
        self.assertEqual(md["actions"], [{"verbose_name": "Mark churned", "action": "mark_churned"}])

    def test_generic_relations_include_feeditem_and_externalobject(self):
        md = build_model_metadata(Ticket)
        by_name = {rel["name"]: rel for rel in md["relations"]}
        self.assertEqual(by_name["feeditem"]["related_model"], "FeedItem")
        self.assertEqual(by_name["feeditem"]["related_model_type"], "FEI")
        self.assertEqual(by_name["feeditem"]["field_name"], "parent_object")
        self.assertEqual(by_name["externalobject"]["related_model"], "ExternalObject")
        self.assertEqual(by_name["externalobject"]["related_model_type"], "EXT")
        self.assertEqual(by_name["externalobject"]["field_name"], "related_object")

    @override_settings(
        CRUDKIT_EXTRA_GENERIC_RELATIONS=[{"model": "crudkit.WorkLog", "field_name": "related_object", "name": "worklog"}]
    )
    def test_extra_generic_relations_setting(self):
        """Project-supplied generic relations (e.g. the CRM's Task) are added
        via the CRUDKIT_EXTRA_GENERIC_RELATIONS setting."""
        md = build_model_metadata(Ticket)
        by_name = {rel["name"]: rel for rel in md["relations"]}
        self.assertIn("worklog", by_name)
        self.assertEqual(by_name["worklog"]["related_model"], "WorkLog")
        self.assertEqual(by_name["worklog"]["related_model_type"], "WLG")
        self.assertEqual(by_name["worklog"]["field_name"], "related_object")

    def test_extra_generic_relations_absent_by_default(self):
        md = build_model_metadata(Ticket)
        self.assertNotIn("worklog", {rel["name"] for rel in md["relations"]})


class BuildInstanceMetadataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="metainst", password="pw")
        cls.topic = Topic.objects.create(name="Billing", created_by=cls.user, updated_by=cls.user)
        cls.customer_alice = Customer.objects.create(name="Alice", created_by=cls.user, updated_by=cls.user)
        cls.customer_bob = Customer.objects.create(name="Bob", created_by=cls.user, updated_by=cls.user)

    def _make_ticket(self, **kw):
        return Ticket.objects.create(
            subject="Demo",
            created_by=self.user,
            updated_by=self.user,
            **kw,
        )

    def test_skips_audit_fields(self):
        md = build_instance_metadata(self._make_ticket())
        for skip in ("id", "created_at", "updated_at", "created_by", "updated_by", "deleted"):
            self.assertNotIn(skip, md["fields"], f"{skip} must be hidden from the LLM")

    def test_actions_collapsed_to_name_list(self):
        md = build_instance_metadata(self.customer_alice)
        self.assertEqual(md["actions"], list(Customer()._actions.keys()))
        self.assertEqual(md["actions"], ["mark_churned"])

    def test_fk_current_collapses_to_id_display(self):
        ticket = self._make_ticket(customer=self.customer_alice)
        md = build_instance_metadata(ticket)
        customer_current = md["fields"]["customer"]["current"]
        self.assertEqual(customer_current, {"id": ticket.customer_id, "display": "Alice"})

    def test_fk_choices_listed_for_small_tables(self):
        md = build_instance_metadata(self._make_ticket())
        customer_choices = md["fields"]["customer"]["fk_choices"]
        self.assertIn("options", customer_choices)
        displays = {opt["display"] for opt in customer_choices["options"]}
        self.assertEqual(displays, {"Alice", "Bob"})

    def test_fk_choices_reports_when_too_wide(self):
        """When a FK target has more rows than the limit, the payload must
        tell the model so instead of dumping a huge list."""
        for n in range(FK_CHOICES_LIMIT + 1):
            Customer.objects.create(
                name=f"Customer {n}",
                created_by=self.user,
                updated_by=self.user,
            )
        md = build_instance_metadata(self._make_ticket())
        customer_choices = md["fields"]["customer"]["fk_choices"]
        self.assertIsNone(customer_choices["options"])
        self.assertIn("too many", customer_choices["reason"])

    def test_choice_field_choices_are_flat(self):
        customer = Customer.objects.create(
            name="Churny",
            status=Customer.StatusChoices.CHURNED,
            created_by=self.user,
            updated_by=self.user,
        )
        md = build_instance_metadata(customer)
        status = md["fields"]["status"]
        self.assertEqual(status["current"], "churned")
        self.assertEqual(
            set(status["choices"]),
            {choice for choice, _ in Customer.StatusChoices.choices},
        )

    def test_output_is_json_serialisable(self):
        """The whole pipeline must produce something pydantic-ai can dump.
        json.dumps with default str is a strict-enough proxy."""
        md = build_instance_metadata(self._make_ticket(customer=self.customer_alice))
        json.dumps(md)
