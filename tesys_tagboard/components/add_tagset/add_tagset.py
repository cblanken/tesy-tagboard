from django_components import Component
from django_components import register


@register("add_tagset")
class AddTagsetComponent(Component):
    template_file = "add_tagset.html"
    js_file = "add_tagset.js"

    def get_template_data(self, args, kwargs, slots, context):
        autocomplete_url = kwargs.get("autocomplete_url")
        return {"autocomplete_url": autocomplete_url}
