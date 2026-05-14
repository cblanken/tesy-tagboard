from django_components import Component, register


@register("collection_thumbnail")
class CollectionThumbnailComponent(Component):
    template_file = "collection_thumbnail.html"
    js_file = "collection_thumbnail.js"

    def get_template_data(self, args, kwargs, slots, context):
        collection = kwargs.get("collection")
        return {"collection": collection}
