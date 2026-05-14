"""Test module for everything related to search autocompletion"""

import pytest

from tesys_tagboard.models import Tag, TagAlias, TagCategory
from tesys_tagboard.search import (
    TAG_CATEGORY_DELIMITER,
    PostSearch,
    PostSearchTokenCategory,
    autocomplete_tag_aliases,
    autocomplete_tags,
)


@pytest.mark.django_db
class TestTagAutocomplete:
    def test_autocomplete_included_by_name_partial(self, db):
        tags = autocomplete_tags(Tag.tags.all(), "blue")
        tag_names = [tag.name for tag in tags]
        assert "blue-jeans" in tag_names
        assert "blue" in tag_names
        assert "blue-gray" in tag_names
        assert "blueberry" in tag_names
        assert "red_vs._blue" in tag_names
        assert "sky-blue" in tag_names
        assert len(tag_names) == 6

    def test_autocomplete_partial_with_category(self, db):
        tags = list(autocomplete_tags(Tag.tags.all(), "Peru:"))
        tag_names = [tag.name for tag in tags]
        assert len(tags) == 3
        assert "Huarez" in tag_names
        assert "Pallasca" in tag_names
        assert "Dos_de_Mayo" in tag_names

    def test_autocomplete_partial_with_nested_categories(self, db):
        tags = list(
            autocomplete_tags(
                Tag.tags.all(),
                f"South_America{TAG_CATEGORY_DELIMITER}Peru{TAG_CATEGORY_DELIMITER}",
            )
        )
        tag_names = [tag.name for tag in tags]
        assert "Huarez" in tag_names
        assert "Pallasca" in tag_names
        assert "Dos_de_Mayo" in tag_names

    def test_autocomplete_excluded_by_name_partial(self, db):
        tags = autocomplete_tags(Tag.tags.all(), exclude_partial="blue")
        tag_names = [tag.name for tag in tags]
        assert "blue-jeans" not in tag_names
        assert "blue" not in tag_names
        assert "blue-gray" not in tag_names
        assert "blueberry" not in tag_names
        assert "sky-blue" not in tag_names

    def test_autocomplete_excluded_by_tag_name(self, db):
        tags = autocomplete_tags(
            Tag.tags.all(), exclude_tag_names=["violet", "white", "yellow"]
        )
        tag_names = [tag.name for tag in tags]
        assert "violet" not in tag_names
        assert "white" not in tag_names
        assert "yellow" not in tag_names
        assert "white-rapids" in tag_names
        assert "yellow-flowers" in tag_names
        assert "violet-hyacinth" in tag_names

    def test_autocomplete_excluded_by_tag(self, db):
        copyright_category = TagCategory.objects.get(name="copyright")
        exclude_tags = Tag.tags.filter(category=copyright_category)
        tag_items = autocomplete_tags(Tag.tags.all(), exclude_tags=exclude_tags)
        for item in tag_items:
            assert item.name not in [tag.name for tag in exclude_tags]


@pytest.mark.django_db
class TestTagAliasAutocomplete:
    def test_autocomplete_included_by_name_partial(self, db):
        aliases = autocomplete_tag_aliases(TagAlias.aliases.all(), "blue")
        alias_names = [alias.alias for alias in aliases]
        assert "bluejeans" in alias_names
        assert "gray-blue" in alias_names
        assert "blue-berry" in alias_names
        assert "red_v._blue" in alias_names
        assert "red_vs_blue" in alias_names
        assert "red_x_blue" in alias_names
        assert len(alias_names) == 6

    def test_autocomplete_excluded_by_name_partial(self, db):
        aliases = autocomplete_tag_aliases(
            TagAlias.aliases.all(), exclude_partial="red"
        )
        alias_names = [alias.alias for alias in aliases]
        assert "red_v._blue" not in alias_names
        assert "red_vs_blue" not in alias_names
        assert "red_x_blue" not in alias_names
        assert "r_v._b" in alias_names
        assert "r_vs._b" in alias_names

    def test_autocomplete_excluded_by_alias_name(self, db):
        aliases = autocomplete_tag_aliases(
            TagAlias.aliases.all(),
            exclude_alias_names=["Justin K", "Solomon S", "Z. Zolan"],
        )
        alias_names = [alias.alias for alias in aliases]
        assert "Justin K" not in alias_names
        assert "Solomon S" not in alias_names
        assert "Z. Zolan" not in alias_names

    def test_autocomplete_excluded_by_alias(self, db):
        copyright_category = TagCategory.objects.get(name="copyright")
        exclude_aliases = TagAlias.aliases.filter(tag__category=copyright_category)
        aliases = autocomplete_tag_aliases(
            TagAlias.aliases.all(), exclude_aliases=exclude_aliases
        )

        for alias_item in aliases:
            assert alias_item.alias not in [alias.name for alias in exclude_aliases]


@pytest.mark.django_db
class TestPostAdvancedSearchAutocomplete:
    def test_exclude_already_mentioned_tags(self):
        ps = PostSearch("amber amaranth")
        items = ps.autocomplete("am")
        item_names = [x.name for x in items]
        assert "amaranth-pink" in item_names
        assert "amaranth-purple" in item_names
        assert "amaranth" not in item_names
        assert "amber" not in item_names

    def test_include_tags_and_aliases(self):
        ps = PostSearch("red")
        items = list(ps.autocomplete())

        # Tags
        tag_names = [
            item.name
            for item in items
            if item.token_category == PostSearchTokenCategory.TAG
        ]
        assert "red" in tag_names
        assert "red_vs._blue" in tag_names

        # Aliases
        alias_names = [
            item.alias
            for item in items
            if item.token_category == PostSearchTokenCategory.TAG_ALIAS
        ]
        assert "red_v._blue" in alias_names
        assert "red_vs_blue" in alias_names
        assert "red_x_blue" in alias_names

    def test_exclude_negated_mentioned_tags(self):
        ps = PostSearch("-green")
        items = ps.autocomplete("gree")
        item_names = [x.name for x in items]
        assert "evergreen" in item_names
        assert "lime-green" in item_names
        assert "green" not in item_names

    def test_yes_filters(self):
        ps = PostSearch("")
        items = list(ps.autocomplete(show_filters=True))
        item_categories = {item.token_category for item in items}
        for tc in PostSearchTokenCategory:
            assert tc in item_categories

    def test_no_filters(self):
        ps = PostSearch("")
        items = ps.autocomplete(show_filters=False)
        item_categories = {item.token_category for item in items}
        item_categories.remove(PostSearchTokenCategory.TAG)
        item_categories.remove(PostSearchTokenCategory.TAG_ALIAS)
        for tc in PostSearchTokenCategory:
            assert tc not in item_categories

    def test_complete_with_leading_negation(self):
        ps = PostSearch("blue -blu")
        items = ps.autocomplete("-blu")
        item_names = [x.name for x in items]
        assert "blue-jeans" in item_names
        assert "blue-gray" in item_names
        assert "blueberry" in item_names
        assert "sky-blue" in item_names
