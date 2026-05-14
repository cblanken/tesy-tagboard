from django_components import Component, register


@register("post_gallery")
class PostGalleryComponent(Component):
    template_file = "post_gallery.html"
    js_file = "post_gallery.js"

    def get_template_data(self, args, kwargs, slots, context):
        pager = kwargs.get("pager")

        # Must specificity an querystring arg name to render multiple
        # galleries on a single page
        query_page_arg_name = kwargs.get("query_page_arg_name", "page")
        page = kwargs.get("page")
        page_range = list(pager.get_elided_page_range(page.number, on_each_side=1))

        collections = None
        # Authenticated users can use favorites and collection features
        if self.request.user.is_authenticated:
            collections = self.request.user.collection_set.with_gallery_data()

        return {
            "collections": collections,
            "query_page_arg_name": query_page_arg_name,
            "pager": pager,
            "page": page,
            "page_range": page_range,
        }
