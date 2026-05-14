from django_components import Component, register


@register("create_tag_alias")
class CreateTagAliasComponent(Component):
    template_file = "create_tag_alias.html"
    js_file = "create_tag_alias.js"
