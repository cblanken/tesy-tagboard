from django_components import Component
from django_components import register


@register("create_tag")
class CreateTagComponent(Component):
    template_file = "create_tag.html"
    js_file = "create_tag.js"

    def get_template_data(self, args, kwargs, slots, context):
        return {}
