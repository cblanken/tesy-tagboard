from django_components import Component, register


@register("create_collection")
class CreateCollectionComponent(Component):
    template_file = "create_collection.html"
    js_file = "create_collection.js"

    def get_template_data(self, args, kwargs, slots, context):
        return {}
