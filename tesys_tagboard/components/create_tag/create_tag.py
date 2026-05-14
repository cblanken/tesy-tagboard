from django_components import Component, register

from tesys_tagboard.enums import RatingLevel


@register("create_tag")
class CreateTagComponent(Component):
    template_file = "create_tag.html"
    js_file = "create_tag.js"

    def get_template_data(self, args, kwargs, slots, context):
        categories = kwargs.get("categories")
        return {"categories": categories, "rating_levels": list(RatingLevel)}
