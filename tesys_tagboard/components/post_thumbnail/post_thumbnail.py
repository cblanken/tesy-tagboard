from django_components import Component, register


@register("post_thumbnail")
class PostThumbnailComponent(Component):
    template_file = "post_thumbnail.html"
    css_file = "post_thumbnail.css"
    js_file = "post_thumbnail.js"

    def get_template_data(self, args, kwargs, slots, context):
        post = kwargs.get("post")
        max_tags = kwargs.get("max_tags", 16)
        tags = post.tags.all()[:max_tags]
        collections = kwargs.get("collections")

        return {
            "post": post,
            "tags": tags,
            "max_tags": max_tags,
            "collections": collections,
        }
