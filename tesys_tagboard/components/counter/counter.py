from django.templatetags.static import static
from django_components import Component, register


@register("counter")
class CounterComponent(Component):
    template_file = "counter.html"
    js_file = "counter.js"

    def get_template_data(self, args, kwargs, slots, context):
        num = str(self.kwargs.get("num"))
        ext = "png"

        img_urls = [(digit, static(f"images/counter/{digit}.{ext}")) for digit in num]
        return {
            "num": num,
            "img_urls": img_urls,
        }
