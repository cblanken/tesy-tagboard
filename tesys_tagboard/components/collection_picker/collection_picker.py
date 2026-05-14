from django_components import Component, register


@register("collection_picker")
class CollectionPickerComponent(Component):
    template_file = "collection_picker.html"
    js_file = "collection_picker.js"

    def get_template_data(self, args, kwargs, slots, context):
        post = kwargs.get("post")
        collections = kwargs.get("collections")
        return {"collections": collections, "post": post}
