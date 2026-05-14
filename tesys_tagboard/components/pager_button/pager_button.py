from django_components import Component, register


@register("pager_button")
class PagerButtonComponent(Component):
    template_file = "pager_button.html"
    js_file = "pager_button.js"

    def get_template_data(self, args, kwargs, slots, context):
        page_num = self.kwargs.get("page_num")
        text = self.kwargs.get("text")
        disabled = self.kwargs.get("disabled", False)
        active = self.kwargs.get("active", False)
        query_page_arg_name = self.kwargs.get("query_page_arg_name")
        return {
            "page_num": page_num,
            "text": text,
            "query_page_arg_name": query_page_arg_name,
            "disabled": disabled,
            "active": active,
        }
