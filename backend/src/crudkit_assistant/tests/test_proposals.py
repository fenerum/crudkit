"""
Tests for the AssistantProposal model and the safety invariant:
proposal tools must NOT mutate the target object; the mutation only happens
in apply(), which the WebSocket consumer calls when the user clicks Confirm.
"""

import asyncio

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from crudkit_assistant import tools
from crudkit_assistant.deps import AssistantDeps
from crudkit_assistant.models import AssistantProposal
from tests.testapp.models import Customer

User = get_user_model()


def grant_customer_permissions(user):
    permissions = Permission.objects.filter(
        content_type__app_label=Customer._meta.app_label,
        codename__in=["view_customer", "change_customer"],
    )
    user.user_permissions.add(*permissions)


class ProposalSafetyTests(TestCase):
    """Verify proposal tools persist a PENDING row and do NOT mutate."""

    def setUp(self):
        self.user = User.objects.create_user(username="staff", password="x")
        grant_customer_permissions(self.user)
        self.customer = Customer.objects.create(
            name="Original",
            created_by=self.user,
            updated_by=self.user,
        )
        # Customer.pk is a formatted CK id ("CUS<n>"); TYPE_ID is "CUS".
        self.deps = AssistantDeps(
            user_id=self.user.pk,
            object_type_id="CUS",
            object_pk=self.customer.pk,
            session_key="testsession",
        )
        # The runner normally attaches an asyncio.Queue here. The proposal
        # tools call `await outbox.put(...)`; we set a real queue so that
        # path runs end-to-end.
        self.deps._outbox = asyncio.Queue()  # type: ignore[attr-defined]

    def _run_tool(self, coro_fn, *args, **kwargs):
        ctx = _FakeCtx(self.deps)
        return async_to_sync(coro_fn)(ctx, *args, **kwargs)

    def test_propose_patch_does_not_mutate(self):
        result = self._run_tool(tools.propose_patch, {"name": "Renamed"}, "model thinks so")

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Original")  # not mutated

        proposal = AssistantProposal.objects.get(session_key="testsession")
        self.assertEqual(proposal.status, AssistantProposal.Status.PENDING)
        self.assertEqual(proposal.kind, AssistantProposal.Kind.PATCH)
        self.assertEqual(proposal.payload, {"fields": {"name": "Renamed"}})
        self.assertIn(str(proposal.id), result)

    def test_propose_action_does_not_mutate(self):
        self._run_tool(tools.propose_action, "mark_churned", "Customer stopped paying")

        self.customer.refresh_from_db()
        # mark_churned() would have transitioned status to CHURNED. That must
        # not happen at proposal time.
        self.assertNotEqual(self.customer.status, Customer.StatusChoices.CHURNED)

        proposal = AssistantProposal.objects.get(session_key="testsession")
        self.assertEqual(proposal.status, AssistantProposal.Status.PENDING)
        self.assertEqual(proposal.kind, AssistantProposal.Kind.ACTION)
        self.assertEqual(proposal.payload, {"action": "mark_churned"})

    def test_propose_create_note_does_not_mutate(self):
        from crudkit.models import FeedItem

        self._run_tool(tools.propose_create_note, "Customer wants a callback", "")

        self.assertFalse(FeedItem.objects.filter(parent_object_id=self.customer.pk).exists())
        proposal = AssistantProposal.objects.get(session_key="testsession")
        self.assertEqual(proposal.status, AssistantProposal.Status.PENDING)
        self.assertEqual(proposal.kind, AssistantProposal.Kind.NOTE)


class ProposalApplyTests(TestCase):
    """Verify apply() / skip() flip the right state and actually mutate."""

    def setUp(self):
        self.user = User.objects.create_user(username="staff", password="x")
        grant_customer_permissions(self.user)
        self.customer = Customer.objects.create(
            name="Original",
            created_by=self.user,
            updated_by=self.user,
        )

    def _make_proposal(self, kind, payload, label="test"):
        from django.contrib.contenttypes.models import ContentType

        return AssistantProposal.objects.create(
            target_content_type=ContentType.objects.get_for_model(Customer),
            target_object_id=self.customer.pk,
            session_key="s",
            kind=kind,
            label=label,
            payload=payload,
            created_by=self.user,
            updated_by=self.user,
        )

    def test_apply_patch_updates_field(self):
        proposal = self._make_proposal(
            AssistantProposal.Kind.PATCH,
            {"fields": {"name": "Renamed"}},
            label="Rename customer",
        )

        proposal.apply(self.user)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Renamed")
        self.assertEqual(proposal.status, AssistantProposal.Status.CONFIRMED)
        self.assertEqual(proposal.outcome.get("kind"), "patch")
        self.assertIn("name", proposal.outcome.get("applied") or [])

    def test_apply_action_runs_crm_action(self):
        proposal = self._make_proposal(
            AssistantProposal.Kind.ACTION,
            {"action": "mark_churned"},
            label="Churn",
        )

        proposal.apply(self.user)

        self.assertEqual(proposal.status, AssistantProposal.Status.CONFIRMED)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, Customer.StatusChoices.CHURNED)

    def test_apply_create_note_creates_feeditem(self):
        from crudkit.models import FeedItem

        proposal = self._make_proposal(
            AssistantProposal.Kind.NOTE,
            {"body": "Followup tomorrow"},
            label="Add note",
        )

        proposal.apply(self.user)

        self.assertEqual(proposal.status, AssistantProposal.Status.CONFIRMED)
        fei = FeedItem.objects.get(pk=proposal.outcome["feeditem_id"])
        self.assertEqual(fei.body, "Followup tomorrow")
        # customer.pk is the formatted "CUS<n>"; FeedItem.parent_object_id
        # stores the raw integer.
        from crudkit.models import parse_ck_id

        _, customer_raw_pk = parse_ck_id(self.customer.pk)
        self.assertEqual(fei.parent_object_id, customer_raw_pk)

    def test_apply_rejects_unknown_action(self):
        proposal = self._make_proposal(
            AssistantProposal.Kind.ACTION,
            {"action": "no_such_action"},
            label="Bogus",
        )

        proposal.apply(self.user)

        self.assertEqual(proposal.status, AssistantProposal.Status.FAILED)
        self.assertIn("not available", proposal.outcome.get("error", ""))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Original")

    def test_apply_patch_rejects_unknown_field(self):
        proposal = self._make_proposal(
            AssistantProposal.Kind.PATCH,
            {"fields": {"not_a_real_field": 1}},
            label="Bogus",
        )

        proposal.apply(self.user)

        self.assertEqual(proposal.status, AssistantProposal.Status.FAILED)
        self.assertIn("not_a_real_field", proposal.outcome.get("error", ""))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Original")

    def test_apply_patch_resolves_fk_by_int_pk(self):
        """Bug: setattr(instance, 'fk', 2) fails because Django wants the
        related instance. The DRF serializer should turn the int PK into the
        actual User row."""
        other = User.objects.create_user(username="other", password="x")
        proposal = self._make_proposal(
            AssistantProposal.Kind.PATCH,
            {"fields": {"owner": other.pk}},
            label="Reassign",
        )

        proposal.apply(self.user)

        self.assertEqual(
            proposal.status,
            AssistantProposal.Status.CONFIRMED,
            f"FK PK assign failed: {proposal.outcome}",
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.owner_id, other.pk)

    def test_apply_patch_resolves_fk_by_numeric_string(self):
        """The LLM sometimes stringifies PKs. Serializer should still cope."""
        other = User.objects.create_user(username="strpk", password="x")
        proposal = self._make_proposal(
            AssistantProposal.Kind.PATCH,
            {"fields": {"owner": str(other.pk)}},
            label="Reassign",
        )

        proposal.apply(self.user)

        self.assertEqual(
            proposal.status,
            AssistantProposal.Status.CONFIRMED,
            f"FK string PK assign failed: {proposal.outcome}",
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.owner_id, other.pk)

    def test_apply_patch_unwraps_fk_dict_from_describe_object(self):
        """The model often echoes the `describe_object` shape for FK fields
        — `{"owner": {"id": <pk>, "display": "..."}}`. The DRF serializer
        expects a bare PK, so the executor must unwrap the dict first."""
        other = User.objects.create_user(username="dictfk", password="x")
        proposal = self._make_proposal(
            AssistantProposal.Kind.PATCH,
            {"fields": {"owner": {"id": other.pk, "display": "dictfk"}}},
            label="Reassign",
        )

        proposal.apply(self.user)

        self.assertEqual(
            proposal.status,
            AssistantProposal.Status.CONFIRMED,
            f"FK dict unwrap failed: {proposal.outcome}",
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.owner_id, other.pk)

    def test_apply_patch_rejects_invalid_fk_pk(self):
        proposal = self._make_proposal(
            AssistantProposal.Kind.PATCH,
            {"fields": {"owner": 999999}},
            label="Reassign",
        )

        proposal.apply(self.user)

        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.owner_id)
        self.assertEqual(proposal.status, AssistantProposal.Status.FAILED)
        self.assertIn("does not exist", proposal.outcome["error"])

    def test_skip_does_not_mutate(self):
        proposal = self._make_proposal(
            AssistantProposal.Kind.PATCH,
            {"fields": {"name": "Renamed"}},
            label="Rename",
        )

        proposal.skip(self.user)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Original")
        self.assertEqual(proposal.status, AssistantProposal.Status.SKIPPED)
        self.assertIsNotNone(proposal.confirmed_at)

    def test_apply_requires_change_permission(self):
        self.user.user_permissions.clear()
        proposal = self._make_proposal(
            AssistantProposal.Kind.PATCH,
            {"fields": {"name": "Renamed"}},
        )

        proposal.apply(self.user)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Original")
        self.assertEqual(proposal.status, AssistantProposal.Status.FAILED)


class FallbackPromptTests(TestCase):
    """A CrudKit model that hasn't set assistant_prompt must still get a
    working agent — the framework supplies a generic prompt."""

    def test_default_prompt_is_empty_string(self):
        from crudkit.models import BaseCrudKitModel

        self.assertEqual(BaseCrudKitModel.CrudKitSettings.assistant_prompt, "")

    def test_get_assistant_prompt_returns_empty_when_not_set(self):
        from crudkit_assistant.utils import get_assistant_prompt

        user = User.objects.create_user(username="u", password="x")
        customer = Customer.objects.create(
            name="X",
            created_by=user,
            updated_by=user,
        )
        # Customer.CrudKitSettings doesn't define assistant_prompt; inherits "".
        self.assertEqual(get_assistant_prompt(customer), "")


class SanitiseToolNameTests(TestCase):
    """Mistral occasionally glues invisible Unicode-Tag characters and the
    args literal onto the tool name, producing things like
    `get_object\\U000e006a{}`. The sanitiser strips them so pydantic-ai can
    match the call back to a registered tool."""

    def test_passthrough_clean_name(self):
        from crudkit_assistant.runner import _sanitise_tool_name

        self.assertEqual(_sanitise_tool_name("describe_object"), "describe_object")

    def test_strips_unicode_tag_character(self):
        from crudkit_assistant.runner import _sanitise_tool_name

        # U+E006A is the tag character we observed in production logs.
        self.assertEqual(_sanitise_tool_name("get_object\U000e006a"), "get_object")

    def test_strips_appended_args_literal(self):
        from crudkit_assistant.runner import _sanitise_tool_name

        self.assertEqual(
            _sanitise_tool_name('get_related\U000e006a{"relation_name": "activity_set"}'),
            "get_related",
        )

    def test_strips_trailing_whitespace_or_paren(self):
        from crudkit_assistant.runner import _sanitise_tool_name

        self.assertEqual(_sanitise_tool_name("describe_object "), "describe_object")
        self.assertEqual(_sanitise_tool_name("describe_object()"), "describe_object")

    def test_empty_input_returns_empty(self):
        from crudkit_assistant.runner import _sanitise_tool_name

        self.assertEqual(_sanitise_tool_name(""), "")


class _FakeCtx:
    """Minimal stand-in for pydantic_ai.RunContext used in tool unit tests."""

    def __init__(self, deps):
        self.deps = deps
