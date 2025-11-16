from django_components import Component
from django_components import register


@register("post_thumbnail")
class PostThumbnailComponent(Component):
    template_file = "post_thumbnail.html"
    js_file = "post_thumbnail.js"
