from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _
from django_components import Component, register

from tesys_tagboard.search import PostSearchTokenCategory

if TYPE_CHECKING:
    from django.contrib.auth.context_processors import PermWrapper
    from django.utils.safestring import SafeString

    from tesys_tagboard.models import Tag, TagAlias


@dataclass
class Action:
    name: str
    display: str
    desc: str
    tag: Tag | None = None
    alias: TagAlias | None = None
    arg: str = ""

    def render(
        self, template_name: str = "tags/tag_actions/tag_action.html", **kwargs
    ) -> SafeString:
        return render_to_string(template_name, context={"action": self, **kwargs})


@register("tag")
class TagComponent(Component):
    template_file = "tag.html"
    js_file = "tag.js"

    def get_template_data(self, args, kwargs, slots, context):
        tag: Tag = kwargs.get("tag")
        alias = kwargs.get("alias")
        tag = alias.tag if alias else kwargs.get("tag")
        perms: PermWrapper | None = context.get("perms")
        if tag is None and alias is None:
            return {}
        size = kwargs.get("size")
        category = tag.category
        extra_actions = kwargs.get("actions", [])
        search_query = (
            f"{reverse('posts')}?q={PostSearchTokenCategory.TAG_ID.value.name}={tag.pk}"
        )
        search_action = Action(
            "search",
            display=_("Search"),
            desc=_("Search for posts with this tag"),
            tag=tag,
            arg=search_query,
        )

        update_tag_action = Action(
            "update-tag",
            display=_("Update tag"),
            desc=_("Update this tag"),
            tag=tag,
        )

        delete_tag_action = Action(
            "delete-tag",
            display=_("Delete tag"),
            desc=_("Delete this tag"),
            tag=tag,
        )

        restore_tag_action = Action(
            "restore-tag",
            display=_("Restore tag"),
            desc=_("Restore this tag"),
            tag=tag,
        )

        actions = [search_action]

        if not tag.deleted and perms and perms["tesys_tagboard"]["change_tag"]:
            actions.append(update_tag_action)

        if not tag.deleted and perms and perms["tesys_tagboard"]["delete_tag"]:
            actions.append(delete_tag_action)

        if tag.deleted and perms and perms["tesys_tagboard"]["restore_deleted_tags"]:
            actions.append(restore_tag_action)

        if alias:
            update_alias_action = Action(
                "update-alias",
                display=_("Update alias"),
                desc=_("Update this tag alias"),
                tag=tag,
                alias=alias,
            )
            delete_alias_action = Action(
                "delete-alias",
                display=_("Delete alias"),
                desc=_("Delete this tag alias"),
                tag=tag,
                alias=alias,
            )

            if perms and perms["tesys_tagboard"]["change_tagalias"]:
                actions.append(update_alias_action)

            if perms and perms["tesys_tagboard"]["delete_tagalias"]:
                actions.append(delete_alias_action)

        actions.extend(extra_actions)

        return {
            "tag": tag,
            "tag_search_query": search_query,
            "size": size,
            "category": category,
            "actions": actions,
            "alias": alias,
        }
