from django_components import Component, register


@register("comment")
class CommentComponent(Component):
    template_file = "comment.html"
    js_file = "comment.js"

    def get_template_data(self, args, kwargs, slots, context):
        comment = kwargs.get("comment")
        return {"comment": comment}
