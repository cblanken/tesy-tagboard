from django.urls import reverse
from django.utils.translation import gettext as _
from django_components import Component, register

from tesys_tagboard.components.tag.tag import Action


@register("add_tagset")
class AddTagsetComponent(Component):
    template_file = "add_tagset.html"
    js_file = "add_tagset.js"

    def get_template_data(self, args, kwargs, slots, context):
        size: str = kwargs.get("size")
        post_url: str = kwargs.get("post_url", reverse("confirm-tagset"))
        autocomplete_url: str = kwargs.get(
            "autocomplete_url", reverse("tag-autocomplete")
        )
        add_tag_enabled: bool = kwargs.get("add_tag_enabled")

        return {
            "size": size,
            "add_tag_enabled": bool(add_tag_enabled),
            "tags": kwargs.get("tags"),
            "actions": [
                Action(
                    "remove",
                    # Translators: remove tag action
                    _("Remove"),
                    # Translators: remove tag action description
                    _("Remove this tag from the tag set"),
                )
            ],
            "tagset_name": kwargs.get("tagset_name", "tagset"),
            "post_url": post_url,
            "autocomplete_url": autocomplete_url,
        }
