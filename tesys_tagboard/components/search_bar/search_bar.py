from django.urls import reverse
from django_components import Component
from django_components import register


@register("search_bar")
class ThemePicker(Component):
    template_file = "search_bar.html"
    js_file = "search_bar.js"

    def get_template_data(self, args, kwargs, slots, context):
        return {"autocomplete_url": reverse(kwargs.get("autocomplete_url"))}
