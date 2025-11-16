import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from itertools import chain

from django.core import validators
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models import QuerySet
from django.utils.regex_helper import _lazy_re_compile
from django.utils.translation import gettext_lazy as _

from .enums import TagCategory
from .models import Post
from .models import Tag


def tag_autocomplete(
    partial: str,
    exclude_tag_names: list[str] | None = None,
    exlude_tags: QuerySet[Tag] | None = None,
) -> QuerySet[Tag]:
    tags = Tag.objects.filter(Q(name__icontains=partial))
    if exclude_tag_names is not None:
        tags = tags.exclude(Q(name__in=exclude_tag_names))

    return tags


@dataclass
class TokenType:
    names: list[str]  # token type allowed name and aliases
    param_validator: validators.RegexValidator | None


tag_name_validator = validators.RegexValidator(
    _lazy_re_compile(r"^-?[a-zA-Z_]]\Z"),
    message=_("Enter a valid tag."),
)

username_validator = validators.RegexValidator(
    _lazy_re_compile(r"^-?[a-zA-Z_]]\Z"),
    message=_("Enter a valid username."),
)


class TokenCategory(Enum):
    """Enum for categorizing tokens in Post search queries
    Note that these prefixes (besides the default `tag`)
    will be shadowed by any conflicting Tag prefixes since
    Tags take precendence when searching.
    """

    tag = TokenType([""], tag_name_validator)  # default tag (no prefix)
    comment_count = TokenType(["comment_count", "cc"], validators.integer_validator)
    fav = TokenType(["favorite", "fav"], username_validator)  # favorited by given user
    fav_count = TokenType(["favorite_count", "fav_count"], username_validator)
    height = TokenType(["height", "h"], validators.integer_validator)
    width = TokenType(["width", "w"], validators.integer_validator)
    rating = TokenType(["rating", "r"], validators.integer_validator)
    source = TokenType(["source", "src"], validators.URLValidator())
    uploader = TokenType(["uploader", "up"], username_validator)
    # TODO: other search options

    @classmethod
    def select(cls, name: str):
        """Select token by name or one of its aliases"""
        for names, token in [(x.value.names, x) for x in TokenCategory]:
            if name in names:
                return token

        return cls.tag

    def is_valid(self) -> bool:
        if validator := self.value.param_validator:
            try:
                validator(self.value)
            except ValidationError:
                return False
        return True


@dataclass
class NamedToken:
    category: TokenCategory
    value: str
    prefix: str = ""
    negate: bool = False


@dataclass
class AutocompleteItem:
    token_category: TokenCategory
    name: str
    tag_category: TagCategory | None = None
    tag_id: int | None = None
    alias: str = ""


class PostSearch:
    """Class to model a Post search query
    Validates query and retrieves autocompletion and query results

    Post search queries can be represented by a regular query string
    """

    def __init__(self, query: str, tag_prefixes: list[str], max_tags: int = 20):
        self.query = query
        tokens = re.split(r"\s+;\s+", self.query)
        self.max_tags = max_tags
        self.include_tag_names: list[str] = []
        self.exclude_tag_names: list[str] = []
        self.include_tags: QuerySet[Tag] | None = None
        self.exclude_tags: QuerySet[Tag] | None = None
        for token in tokens:
            # Parse named tokens and simple tags
            if len(token) > 0:
                prefix, *rest = token.split(":")
                negate: bool = prefix[0] == "-"
                if len(rest) == 0 or prefix in tag_prefixes:
                    # Token with no prefix (category)
                    named_token = NamedToken(
                        TokenCategory.tag, prefix, prefix="", negate=negate
                    )
                elif len(rest) == 1:
                    # Token with a prefix
                    token_category = TokenCategory.select(prefix)
                    named_token = NamedToken(
                        token_category, rest[0], prefix=prefix, negate=negate
                    )
                else:
                    token_category = TokenCategory.select(prefix)
                    named_token = NamedToken(
                        token_category, "".join(rest), prefix=prefix, negate=negate
                    )

                if named_token.category is TokenCategory.tag:
                    if negate:
                        self.exclude_tag_names.append(named_token.value)
                        # TODO: also search TagAliases
                        self.exclude_tags = Tag.objects.filter(
                            name__in=self.exclude_tag_names,
                            category=TagCategory.select(named_token.prefix),
                        )
                    else:
                        self.include_tag_names.append(named_token.value)
                        # TODO: also search TagAliases
                        self.include_tags = Tag.objects.filter(
                            name__in=self.include_tag_names,
                            category=TagCategory.select(named_token.prefix),
                        )

    def autocomplete(self, partial: str = "") -> Iterable[AutocompleteItem]:
        """Return autocomplete matches base on existing search query and
        the provided `partial`"""
        tags = tag_autocomplete(
            partial, self.exclude_tag_names + self.include_tag_names
        )[: self.max_tags]
        return chain(
            (
                AutocompleteItem(TokenCategory.tag, tag.name, tag.category, tag.pk)
                for tag in tags
            ),
            (
                AutocompleteItem(category, name)
                for name, category in TokenCategory.__members__.items()
                if partial in name
            ),
        )

    def get_posts(self):
        return Post.objects.filter(
            Q(tags__in=self.include_tag_names) & ~Q(tags__in=self.exclude_tag_names)
        )
