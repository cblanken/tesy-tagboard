from django_components import Component, register


@register("pager")
class PagerComponent(Component):
    template_file = "pager.html"
    js_file = "pager.js"

    def get_template_data(self, args, kwargs, slots, context):
        pager = self.kwargs.get("pager")
        page = self.kwargs.get("page")
        query_page_arg_name = self.kwargs.get("query_page_arg_name", "page")
        return {
            "pager": pager,
            "page": page,
            "query_page_arg_name": query_page_arg_name,
        }
