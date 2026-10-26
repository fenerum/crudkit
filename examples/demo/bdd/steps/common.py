"""Steps every journey uses: who is signed in, which records exist, going
somewhere, filling in forms, and what is on the screen."""

import re

from playwright.sync_api import expect
from pytest_bdd import given, then, when

from bdd.world import EMAIL, PASSWORD, USERNAME, phrase, sign_in

# People. Alice is the demo's seeded administrator.


@given(phrase("{name:Actor} is signed in"))
def signed_in():
    """Every scenario starts signed in (see conftest.py); this names who that is."""


@given(phrase("{name:Actor} is not signed in"))
def not_signed_in(world, browser, base_url, request):
    context = browser.new_context(base_url=base_url)
    request.addfinalizer(context.close)
    world.page = context.new_page()


@when(phrase("{name:Actor} signs in"))
def signs_in(world):
    sign_in(world.page, USERNAME, PASSWORD)


@when(phrase("{name:Actor} signs in with a wrong password"))
def signs_in_wrongly(world):
    sign_in(world.page, USERNAME, f"not-{PASSWORD}")


@then(phrase("{name:Actor} is asked to sign in"))
def asked_to_sign_in(world):
    expect(world.page).to_have_url(re.compile(r"/login$"))
    expect(world.page.get_by_role("button", name="Sign in")).to_be_visible()


@then(phrase("{name:Actor} is shown as signed in"))
def shown_as_signed_in(world):
    expect(world.page.get_by_role("link", name=re.compile(re.escape(EMAIL)))).to_be_visible()


# Records, created through the API as setup


@given(phrase('{article:A} {model:Model} "{label:Q}"'))
def a_record(world, model, label):
    world.create(model, label)


@given(phrase('{article:A} {model:Model} "{label:Q}" with {field:Words} "{value:Q}"'))
def a_record_with_one_value(world, model, label, field, value):
    world.create(model, label, {field: value})


@given(phrase('{article:A} {model:Model} "{label:Q}" with:'))
def a_record_with_values(world, model, label, datatable):
    """A table of `| field | value |` rows; fields and choices as the screen shows them."""
    world.create(model, label, dict(datatable))


@given(phrase('the {field:Words} of "{label:Q}" was changed to "{value:Q}"'))
@when(phrase('the {field:Words} of "{label:Q}" is changed to "{value:Q}" elsewhere'))
@when(phrase('the {field:Words} of "{label:Q}" are changed to "{value:Q}" elsewhere'))
def changed_elsewhere(world, field, label, value):
    """A change made outside this browser tab (through the API)."""
    record_id = world.id(label)
    spec = world.api.field(record_id[:3], field)
    world.api.update(record_id, {spec["name"]: world.api_value(spec, value)})


@given(phrase('{name:Actor} deleted "{label:Q}"'))
def deleted(world, label):
    world.api.delete(world.id(label))


# Going somewhere


@given(phrase("{name:Actor} is on the dashboard"))
@when(phrase("{name:Actor} goes to the dashboard"))
def on_the_dashboard(world):
    world.page.goto("/")
    shown_as_signed_in(world)


@given(phrase("{name:Actor} is on the {model:Model} list"))
@when(phrase("{name:Actor} opens the {model:Model} list"))
def opens_a_list(world, model):
    world.page.goto(f"/{model}")


@given(phrase('{name:Actor} is on the page of "{label:Q}"'))
@when(phrase('{name:Actor} opens "{label:Q}"'))
def opens_a_record(world, label):
    world.open(label)


@when(phrase('{name:Actor} follows the link "{text:Q}"'))
def follows_a_link(world, text):
    world.main.get_by_role("link", name=world.text(text)).first.click()


@when(phrase("{name:Actor} reloads the page"))
def reloads(world):
    world.page.reload()


def press(world, key):
    """In the innermost open form if there is one, as when typing in it."""
    dialogs = world.page.get_by_role("dialog")
    if dialogs.count():
        dialogs.last.get_by_role("textbox").first.press(key)
    else:
        world.page.keyboard.press(key)


@when(phrase("{name:Actor} presses Escape"))
def presses_escape(world):
    press(world, "Escape")


@when(phrase("{name:Actor} presses Enter"))
def presses_enter(world):
    press(world, "Enter")


@then(phrase("{name:Actor} is on the dashboard"))
def is_on_the_dashboard(world):
    expect(world.page).to_have_url(re.compile(r"^[^?#]*//[^/]+/$"))
    expect(world.main.get_by_role("heading", name="Dashboard")).to_be_visible()


@then(phrase("{name:Actor} is on the {model:Model} list"))
def is_on_a_list(world, model):
    expect(world.page).to_have_url(re.compile(rf"/{model}$"))


@then(phrase('{name:Actor} is on the page of "{label:Q}"'))
def is_on_the_page_of(world, label):
    world.expect_on_page_of(label)


# What is on the screen


@then(phrase("{name:Actor} sees {texts:QList}"))
def sees(world, texts):
    for text in texts:
        expect(world.visible_text(text).first).to_be_visible()


@then(phrase("{name:Actor} does not see {texts:QList}"))
def does_not_see(world, texts):
    for text in texts:
        expect(world.visible_text(text)).to_have_count(0)


@then(phrase('{name:Actor} is told "{message:Q}"'))
def is_told(world, message):
    """A notification, wherever on the page it shows up."""
    expect(world.visible_text(message, world.page).first).to_be_visible()


@then(phrase('the page is titled "{title:Q}"'))
def page_title(world, title):
    expect(world.page).to_have_title(world.text(title))


@then(phrase('the header shows "{text:Q}"'))
def header_shows(world, text):
    expect(world.visible_text(text, world.banner).first).to_be_visible()


# Forms


def form_scope(world):
    """The innermost open form: the top dialog when one is open, else the page."""
    dialogs = world.page.get_by_role("dialog")
    return dialogs.last if dialogs.count() else world.main


def field_input(world, scope, field):
    """The input of the field a feature calls `field`, on the form being filled in.

    A form can be for any record type (a dialog for a book on a reading's
    form), so this matches the field of whichever type the form is for.
    """
    selector = ", ".join(f'input[name="{name}"]' for name in world.api.field_names(field))
    return scope.locator(selector)


@when(phrase('{name:Actor} fills in the {field:Words} "{value:Q}"'))
def fills_in(world, field, value):
    """Typing into the field that labels a record names a new one: see `World.name_for`."""
    text = world.name_for(value) if field == "name" else world.text(value)
    field_input(world, form_scope(world), field).fill(text)


def searchable_select(world, field):
    """The searchable select of `field` on the innermost form; its hidden input sits next to it."""
    return field_input(world, form_scope(world), field).locator("xpath=..").get_by_role("combobox")


@when(phrase('{name:Actor} picks "{value:Q}" as the {field:Words}'))
def picks(world, value, field):
    """Type the value into the select, then pick it from the options."""
    searchable_select(world, field).fill(world.text(value))
    world.page.get_by_role("option", name=world.text(value), exact=True).click()


def submit(world, button):
    """Submit the innermost form; a form in a dialog is done when its dialog closes."""
    dialogs = world.page.get_by_role("dialog")
    open_dialogs = dialogs.count()
    form_scope(world).get_by_role("button", name=button, exact=True).click()
    if open_dialogs:
        expect(dialogs).to_have_count(open_dialogs - 1)


@when(phrase("{name:Actor} creates it"))
def creates_it(world):
    submit(world, "Create")


@when(phrase("{name:Actor} saves it"))
def saves_it(world):
    submit(world, "Save")


@then(phrase('the form has the {field:Words} "{value:Q}"'))
@then(phrase('the form still has the {field:Words} "{value:Q}"'))
def form_has(world, field, value):
    expect(field_input(world, form_scope(world), field)).to_have_value(world.text(value))


@then(phrase('the form shows "{text:Q}"'))
def form_shows(world, text):
    """A value shown on the form that is not typed, like a picked related record."""
    expect(world.visible_text(text, form_scope(world)).first).to_be_visible()
