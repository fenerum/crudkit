from django import template
from django.forms import BoundField
from django.forms.widgets import CheckboxInput, ClearableFileInput, RadioSelect, Select

register = template.Library()


# based on https://stackoverflow.com/questions/29716023/add-class-to-form-field-django-modelform
@register.filter(name="add_form_field_classes")
def add_form_field_classes(value):
    """
    Add provided classes to form field
    :param value: form field
    :param arg: string of classes seperated by ' '
    :return: edited field
    """
    if issubclass(type(value), BoundField):
        new_classes = ""
        input_type = value.field.widget.__class__
        if input_type in [Select]:
            new_classes = "mt-2 block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
        elif input_type == CheckboxInput:
            new_classes = "form-check-input"
        elif input_type == RadioSelect:
            new_classes = ""
        elif input_type == ClearableFileInput:
            new_classes = "w-full rounded-md bg-white px-2.5 py-1.5 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
        else:
            new_classes = "block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"

        if value.errors:
            new_classes = new_classes.replace("border-0", "border-red-500 bg-red-50")
        css_classes = value.field.widget.attrs.get("class", "")
        # check if class is set or empty and split its content to list (or init list)
        if css_classes:
            css_classes = css_classes.split(" ")
        else:
            css_classes = []
        # prepare new classes to list
        args = new_classes.split(" ")
        for a in args:
            if a not in css_classes:
                css_classes.append(a)
        # join back to single string
        return value.as_widget(attrs={"class": " ".join(css_classes)})
    return value
