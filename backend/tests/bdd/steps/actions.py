"""Running a record's actions, the buttons a project adds to a record type.

Phrases this area adds:

- (`When Alice uses the "Mark churned" action on "Acme"` comes from steps/history.py)
- `When Alice tries the action "teleport" on "Acme"`: by its name, for actions the record does not have
- `Given customers have an action "Open billing" that sends people to the billing page`
- `Given customers have an action "Check credit" that answers "Credit OK"`
- `Given customers have an action "Erase" that erases the record`
- `Given customers have an action "Quietly churn" that sets the status to "churned" and answers nothing`
- `Then Alice is taken to "Acme"` / `Then Alice is sent to the billing page`
- `Then Alice gets the answer "Credit OK"`
- `Then "Acme" no longer exists and its removal is logged as "Erase"`

`runs(world, name, action, label)` runs an action by its label, for other areas' steps.
"""

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect
from pytest_bdd import given, then, when
from rest_framework.response import Response

from crudkit.decorators import crm_action
from crudkit.models import ChangeLog
from crudkit_api.services import action_for_label
from tests.bdd.steps.permissions import patch_for_scenario
from tests.bdd.world import phrase

BILLING_PAGE = "https://billing.example.com/"


def _add_action(request, model, verbose_name, method):
    name = verbose_name.lower().replace(" ", "_")
    patch_for_scenario(request, model, name, crm_action(verbose_name)(method))


@given(phrase('{model:Model} have an action "{verbose_name:Q}" that sends people to the billing page'))
def an_action_that_redirects(request, model, verbose_name):
    def open_billing(self, request):
        return HttpResponseRedirect(BILLING_PAGE)

    _add_action(request, model, verbose_name, open_billing)


@given(phrase('{model:Model} have an action "{verbose_name:Q}" that answers "{answer:Q}"'))
def an_action_that_answers(request, model, verbose_name, answer):
    def check(self, request):
        return Response({"message": answer})

    _add_action(request, model, verbose_name, check)


@given(phrase('{model:Model} have an action "{verbose_name:Q}" that erases the record'))
def an_action_that_erases(request, model, verbose_name):
    def erase(self, request):
        self.delete()
        return Response({"message": "Erased"})

    _add_action(request, model, verbose_name, erase)


@given(
    phrase(
        '{model:Model} have an action "{verbose_name:Q}" that sets the {field:Words} to "{value:Q}" and answers nothing'
    )
)
def an_action_that_answers_nothing(request, model, verbose_name, field, value):
    name = field.replace(" ", "_")

    def set_value(self, request):
        setattr(self, name, value)
        self.save(update_fields=[name, "updated_at"])

    _add_action(request, model, verbose_name, set_value)


def runs(world, name, action, label):
    """Run the action labelled `action` (as its button reads) on `label` through the app.
    Shared with other areas' steps."""
    model = type(world.records[label])
    payload = {"action": action_for_label(model, action) or action}
    world.remember(name, world.api(name).post(world.url(label, "action"), payload, format="json"))


@when(phrase('{name:Actor} tries the action "{action:Q}" on "{label:Q}"'))
def tries_an_action(world, name, action, label):
    payload = {"action": action}
    world.remember(name, world.api(name).post(world.url(label, "action"), payload, format="json"))


@then(phrase('{name:Actor} is taken to "{label:Q}"'))
def taken_to(world, name, label):
    assert world.response.status_code == 200, world.response.content
    assert world.response.data["redirect"] == world.ck_id(label), world.response.data


@then(phrase("{name:Actor} is sent to the billing page"))
def sent_to_billing(world, name):
    assert world.response.status_code == 200, world.response.content
    assert world.response.data == {"redirect": BILLING_PAGE}, world.response.data


@then(phrase('"{label:Q}" no longer exists and its removal is logged as "{text:Q}"'))
def removed_and_logged(world, label, text):
    instance = world.records[label]
    assert not type(instance)._base_manager.filter(pk=instance.pk).exists()
    entry = ChangeLog.objects.filter(
        related_content_type=ContentType.objects.get_for_model(type(instance)),
        related_object_id=world.number(label),
    ).last()
    assert (entry.action, entry.label) == (ChangeLog.Action.DELETE, text), (entry.action, entry.label)


@then(phrase('{name:Actor} gets the answer "{answer:Q}"'))
def gets_the_answer(world, name, answer):
    assert world.response.status_code == 200, world.response.content
    assert world.response.data == {"message": answer}, world.response.data
