from django_components import Component
from django_components import register

from tesys_tagboard.models import Tag


@register("post_thumbnail")
class PostThumbnailComponent(Component):
    template_file = "post_thumbnail.html"
    js_file = "post_thumbnail.js"

    def get_template_data(self, args, kwargs, slots, context):
        post = kwargs.get("post")
        max_tags = kwargs.get("max_tags", 15)
        tags = Tag.objects.filter(post=post)
        return {"post": post, "tags": tags, "max_tags": max_tags}
