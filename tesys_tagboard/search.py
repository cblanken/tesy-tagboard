import re
from array import array
from dataclasses import dataclass, field
from enum import Enum
from itertools import chain
from typing import TYPE_CHECKING

from django.conf import settings
from django.core import validators
from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from django.http import QueryDict
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _
from more_itertools import take

from .enums import RatingLevel, SearchBoolean, SupportedMediaType, TokenArgRelation
from .models import Post, PostQuerySet, Tag, TagAlias, TagCategory
from .validators import (
    validate_collection_name,
    validate_file_extension,
    validate_iso_date,
    validate_mimetype,
    validate_positive_int,
    validate_rating_label,
    validate_tag_name,
    validate_tag_token,
    validate_username,
    validate_wildcard_collection_name,
    validate_wildcard_url,
    validate_yes_no,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable

    from colorfield.validators import RegexValidator
    from django_stubs_ext import StrOrPromise

    from tesys_tagboard.users.models import User

TAG_CATEGORY_DELIMITER = settings.TAG_CATEGORY_DELIMITER
MAX_TAG_CATEGORY_DEPTH = settings.MAX_TAG_CATEGORY_DEPTH
VALID_ARG_RELATIONS = "".join([x.value for x in TokenArgRelation])
SEARCH_ARG_QUOTE = settings.SEARCH_ARG_QUOTE
SEARCH_ARG_QUOTE_PATTERN = re.compile(r"([" + SEARCH_ARG_QUOTE + r"])")
FILTER_SPLIT_PATTERN = re.compile(r"([" + VALID_ARG_RELATIONS + r"])")
TOKEN_SPLIT_PATTERN = re.compile(r"\s+")


class SearchTokenFilterNotImplementedError(Exception):
    """Raised when a SearchToken is defined as a TokenCategory but does not have
    a related post search filter implementation"""

    message = "The provided search filter has not been implemented yet."

    def __init__(
        self,
        search_token: SearchTokenBaseCategory,
        *args,
        **kwargs,
    ):
        self.message = f'The provided search filter type: "{search_token.name}" has not been implemented yet.'  # noqa: E501
        super().__init__(self.message, *args, **kwargs)


class SearchTagTokenError(ValidationError):
    message = "The provided tag token is invalid"

    def __init__(self, msg=message, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class SearchTokenNameError(ValidationError):
    message = "The provided name does not match an existing TokenCategory"

    def __init__(self, msg=message, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class UnsupportedSearchOperatorError(ValidationError):
    message = "Unsupported search operator provided"

    def __init__(self, operator: str, token: NamedToken, *args, **kwargs):
        self.message = f'The provided search operator <span class="font-bold font-mono">{operator}</span> is not supported for the token: <span class="font-bold font-mono">{token.name}</span>'  # noqa: E501
        super().__init__(self.message, *args, **kwargs)


class InvalidRatingLabelError(ValidationError):
    message = "The provided rating label does not match an existing RatingLevel"

    def __init__(self, msg=message, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class InvalidMimetypeError(ValidationError):
    mimetypes = ", ".join([smt.value.get_mimetype() for smt in SupportedMediaType])
    message = f"The provided mimetype does not match any of the supported mimetypes: {mimetypes}."  # noqa: E501

    def __init__(self, msg=message, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class InvalidFileExtensionError(ValidationError):
    extensions = ", ".join(chain(*[smt.value.extensions for smt in SupportedMediaType]))
    message = f"The provided file extension does not match any of the supported extensions: {extensions}"  # noqa: E501

    def __init__(self, msg=message, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class UnevenArgumentQuotesError(ValidationError):
    message = _("Search arguments may not contain an odd number of quotes.")

    def __init__(self, msg=message, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


def autocomplete_tags(
    tags: QuerySet[Tag],
    include_partial: str | None = None,
    exclude_partial: str | None = None,
    exclude_tag_names: Iterable[str] | None = None,
    exclude_tags: QuerySet[Tag] | None = None,
) -> Iterable[AutocompleteItem]:
    if include_partial is not None:
        if named_token := NamedToken.from_token_string(include_partial):
            try:
                tag_token = TagToken(named_token)
                tag_filter_expr = tag_token.get_tag_filter_autocomplete_expr()
                tags = tags.filter(tag_filter_expr)
            except ValueError:
                # Ignore any partial that can't be identified as a tag token
                return ()
    if exclude_partial is not None:
        tags = tags.exclude(name__contains=exclude_partial)
    if exclude_tag_names is not None:
        tags = tags.exclude(name__in=exclude_tag_names)
    if exclude_tags is not None:
        tags = tags.exclude(pk__in=exclude_tags)

    return (
        AutocompleteItem(
            PostSearchTokenCategory.TAG,
            tag.name,
            tag.category,
            tag.pk,
            extra=tag.post_count,
        )
        for tag in tags
    )


def autocomplete_tag_aliases(
    aliases: QuerySet[TagAlias],
    include_partial: str | None = None,
    exclude_partial: str | None = None,
    exclude_alias_names: Iterable[str] | None = None,
    exclude_aliases: QuerySet[TagAlias] | None = None,
) -> Generator[AutocompleteItem]:
    if include_partial is not None:
        aliases = TagAlias.aliases.filter(name__icontains=include_partial)
    if exclude_partial is not None:
        aliases = TagAlias.aliases.exclude(name__icontains=exclude_partial)
    if exclude_alias_names is not None:
        aliases = aliases.exclude(name__in=exclude_alias_names)
    if exclude_aliases is not None:
        aliases = aliases.exclude(pk__in=exclude_aliases)

    return (
        AutocompleteItem(
            PostSearchTokenCategory.TAG_ALIAS,
            alias.tag.name,
            alias.tag.category,
            alias.tag.pk,
            alias=alias.name,
            extra=alias.tag.post_count,
        )
        for alias in aliases
    )


@dataclass(kw_only=True)
class SearchTokenBaseCategory:
    """A base class for modeling search tokens"""

    name: str | StrOrPromise
    desc: str | StrOrPromise
    aliases: tuple[str | StrOrPromise, ...]
    arg_validator: validators.RegexValidator | Callable
    allow_wildcard: bool
    allowed_arg_relations: tuple[TokenArgRelation, ...]


@dataclass(kw_only=True)
class SimpleSearchTokenCategory(SearchTokenBaseCategory):
    """A dataclass for defining simple search tokens categories accepting just the
    equal (=) operator and no wildcards. No aliases are included by default."""

    aliases: tuple[str | StrOrPromise, ...] = ()
    allow_wildcard: bool = False
    allowed_arg_relations: tuple[TokenArgRelation, ...] = (TokenArgRelation.EQUAL,)


@dataclass(kw_only=True)
class ComparisonSearchTokenCategory(SearchTokenBaseCategory):
    """A dataclass for defining search token categories that allow the following
    comparison operations of the token argument (>, <, and =)"""

    aliases: tuple[str | StrOrPromise, ...] = ()
    allow_wildcard: bool = False
    allowed_arg_relations: tuple[TokenArgRelation, ...] = (
        TokenArgRelation.EQUAL,
        TokenArgRelation.LESS_THAN,
        TokenArgRelation.GREATER_THAN,
    )


@dataclass(kw_only=True)
class WildcardSearchTokenCategory(SearchTokenBaseCategory):
    """A dataclass for defining search token categories that accept wildcards (*) in
    its token argument"""

    aliases: tuple[str | StrOrPromise, ...] = ()
    allow_wildcard: bool = True
    allowed_arg_relations: tuple[TokenArgRelation, ...] = (TokenArgRelation.EQUAL,)
    wildcard_arg_validator: RegexValidator | Callable | None = None

    def __post_init__(self):
        if self.wildcard_arg_validator is None:
            self.wildcard_arg_validator = self.arg_validator


@dataclass(kw_only=True)
class TagSearchTokenCategory(WildcardSearchTokenCategory):
    """A dataclass for defining tag search tokens."""

    allowed_arg_relations: tuple[TokenArgRelation, ...] = ()


class PostSearchTokenCategory(Enum):
    """Enum for all the supported post search token categories"""

    TAG = TagSearchTokenCategory(
        name="",
        desc=_(
            # Translators: Description for the "wildcard" search token
            "The default (un-named) token. When a plain string without any operator "
            "is given it will be interpreted as a tag name."
        ),
        arg_validator=validate_tag_token,
    )

    TAG_ID = SimpleSearchTokenCategory(
        name=_("tag_id"),
        # Translators: Description for the "tag_id" search token
        desc=_("The ID of a tag."),
        arg_validator=validate_positive_int,
    )

    POST_ID = ComparisonSearchTokenCategory(
        # Translators: Name of the "id" search token
        name=_("id"),
        # Translators: Description for the "id" search token
        desc=_("The ID of a post."),
        arg_validator=validate_positive_int,
    )

    TAG_ALIAS = WildcardSearchTokenCategory(
        # Translators: Name of the "alias" search token
        name=_("alias"),
        # Translators: Description for the "alias" search token
        desc=_("The name of a tag alias."),
        aliases=(
            # Translators: Alias for the "alias" search token
            _("tag_alias"),
        ),
        arg_validator=validate_tag_name,
    )

    TAG_COUNT = ComparisonSearchTokenCategory(
        # Translators: Name of the "tag_count" search token
        name=_("tag_count"),
        # Translators: Description for the "tag_count" search token
        desc=_("The number of tags on a post."),
        aliases=(
            # Translators: Alias for the "tag_count" search token
            _("tc"),
        ),
        arg_validator=validate_positive_int,
    )

    COMMENT_BY = WildcardSearchTokenCategory(
        # Translators: Name of the "comment_by" search token
        name=_("comment_by"),
        # Translators: Description for the "comment_by" search token
        desc=_("The username of a user that has commented on a post"),
        aliases=(
            # Translators: Alias for the "comment_by" search token
            _("comment"),
            # Translators: Alias for the "comment_by" search token
            _("cb"),
        ),
        arg_validator=validate_username,
    )

    COMMENT_COUNT = ComparisonSearchTokenCategory(
        # Translators: Name of the "comment_count" search token
        name=_("comment_count"),
        # Translators: Description for the "comment_count" search token
        desc=_("The number of comments on a post."),
        aliases=(
            # Translators: Alias for the "comment_count" search token
            _("cc"),
        ),
        arg_validator=validate_positive_int,
    )

    FAV_COUNT = ComparisonSearchTokenCategory(
        # Translators: Name of the "fav_count" search token
        name=_("favorite_count"),
        # Translators: Description for the "fav_count" search token
        desc=_("The number of favorites recieved by a post."),
        aliases=(
            # Translators: Alias for the "fav_count" search token
            _("fav_count"),
            # Translators: Alias for the "fav_count" search token
            _("fc"),
        ),
        arg_validator=validate_positive_int,
    )

    HEIGHT = ComparisonSearchTokenCategory(
        # Translators: Name of the "height" search token
        name=_("height"),
        # Translators: Description for the "height" search token
        desc=_("The height of a Post (only applies to images and videos)."),
        aliases=(
            # Translators: Alias for the "height" search token
            _("h"),
        ),
        arg_validator=validators.integer_validator,
    )

    WIDTH = ComparisonSearchTokenCategory(
        # Translators: Name of the "width" search token
        name=_("width"),
        # Translators: Description for the "width" search token
        desc=_("The width of a Post (only applies to images and videos)."),
        aliases=(
            # Translators: Alias for the "width" search token
            _("w"),
        ),
        arg_validator=validators.integer_validator,
    )

    RATING_LABEL = SimpleSearchTokenCategory(
        # Translators: Name of the "rating_label" search token
        name=_("rating_label"),
        # Translators: Description for the "rating_label" search token
        desc=_(
            "The rating of a Post. Accepts one of safe, unrated, questionable, "
            "and explicit."
        ),
        aliases=(
            # Translators: Alias for the "rating_label" search token
            _("rate"),
            # Translators: Alias for the "rating_label" search token
            _("r"),
        ),
        arg_validator=validate_rating_label,
    )

    RATING_NUM = ComparisonSearchTokenCategory(
        name=_("rating_num"),
        desc=_("The rating level of a post."),
        arg_validator=validators.integer_validator,
    )

    SOURCE = WildcardSearchTokenCategory(
        # Translators: Name of the "source" search token
        name=_("source"),
        # Translators: Description for the "source" search token
        desc=_("The source url of a post."),
        aliases=(
            # Translators: Alias for the "source" search token
            _("src"),
        ),
        arg_validator=validators.URLValidator(),
        wildcard_arg_validator=validate_wildcard_url,
    )

    POSTED_BY = WildcardSearchTokenCategory(
        # Translators: Name of the "posted_by" search token
        name=_("posted_by"),
        # Translators: Description for the "posted_by" search token
        desc=_("The username of the uploader of a post."),
        aliases=(
            # Translators: Alias for the "posted_by" search token
            _("uploaded_by"),
        ),
        arg_validator=validate_username,
    )

    POSTED_ON = ComparisonSearchTokenCategory(
        # Translators: Name of the "posted_on" search token
        name=_("posted_on"),
        # Translators: Description for the "posted_on" search token
        desc=_("The date the post was posted on."),
        aliases=(
            # Translators: Alias for the "posted_on" search token
            _("uploaded_on"),
        ),
        arg_validator=validate_iso_date,
    )

    MIMETYPE = SimpleSearchTokenCategory(
        # Translators: Name of the "mimetype" search token
        name=_("mimetype"),
        # Translators: Description for the "mimetype" search token
        desc=_("The MIME type of the post's file."),
        aliases=(
            # Translators: Alias for the "mimetype" search token
            _("mime"),
        ),
        arg_validator=validate_mimetype,
    )

    FILE_EXTENSION = SimpleSearchTokenCategory(
        # Translators: Name of the "file_extension" search token
        name=_("file_extension"),
        # Translators: Description for the "file_extension" search token
        desc=_("The file extension of the post's related file."),
        aliases=(
            # Translators: Alias for the "file_extension" search token
            _("extension"),
            # Translators: Alias for the "file_extension" search token
            _("ext"),
        ),
        arg_validator=validate_file_extension,
    )

    COLLECTION_ID = ComparisonSearchTokenCategory(
        # Translators: Name of the "collection_id" search token
        name=_("collection_id"),
        # Translators: Description for the "collection_id" search token
        desc=_("The ID of a collection."),
        arg_validator=validate_positive_int,
    )

    COLLECTION = SimpleSearchTokenCategory(
        # Translators: Name of the "collection" search token
        name=_("collection"),
        # Translators: Description for the "collection" search token
        desc=_("Whether or not a post is part of a collection (yes/no)."),
        aliases=(
            # Translators: Alias for the "collection" search token
            _("in_collection"),
        ),
        arg_validator=validate_yes_no,
    )

    COLLECTION_NAME = WildcardSearchTokenCategory(
        # Translators: Name of the "collection_name" search token
        name=_("collection_name"),
        # Translators: Description for the "collection_name" search token
        desc=_("A collection's name."),
        arg_validator=validate_collection_name,
        wildcard_arg_validator=validate_wildcard_collection_name,
    )

    PARENT = SimpleSearchTokenCategory(
        # Translators: Name of the "parent" search token
        name=_("parent"),
        # Translators: Description for the "parent" search token
        desc=_("Whether or not a post has a parent (yes/no)."),
        arg_validator=validate_yes_no,
    )

    PARENT_ID = SimpleSearchTokenCategory(
        # Translators: Name of the "parent_id" search token
        name=_("parent_id"),
        # Translators: Description for the "parent_id" search token
        desc=_("Whether or not a post has a parent matching the given post ID."),
        arg_validator=validate_positive_int,
    )

    CHILD = SimpleSearchTokenCategory(
        # Translators: Name of the "children" search token
        name=_("children"),
        # Translators: Description for the "children" search token
        desc=_("Whether or not a post has any children (yes/no)."),
        aliases=(
            # Translators: Alias for the "children" search token
            _("child"),
        ),
        arg_validator=validate_yes_no,
    )

    CHILD_ID = SimpleSearchTokenCategory(
        # Translators: Name of the "child_id" search token
        name=_("child_id"),
        # Translators: Description for the "child_id" search token
        desc=_("Whether or not a post has a child post matching the given post ID."),
        arg_validator=validate_positive_int,
    )

    @classmethod
    def select(cls, name: str) -> PostSearchTokenCategory:
        """Select token category by name or one of its aliases

        Raises: `SearchTokenNameError`
        """
        for tc, name_and_aliases in [
            (tc, [tc.value.name, *tc.value.aliases])
            for tc in PostSearchTokenCategory.__members__.values()
        ]:
            if name in name_and_aliases:
                return tc

        raise SearchTokenNameError


class TagToken:
    """A search token identified as a tag token.

    The input string requires additional parsing to identify any categories in a tag
    token and it's name. Categories are delimited by a colon ":" with the final element
    corresponding the tag's `name`

    For example `country:territory:city` results in:
    ```python
    categories [0] = country
    categories [1] = territory
    categories [2] = city
    ```
    where "country" is the parent category, "territory" a sub category, and "city"
    is the name of the tag.

    Note: TagToken objects should only be created from a NamedToken since the majority
    of token validation is done by the NamedToken initialization..

    Args:
        named_token: NamedToken

    Raises:
        `ValueError`
        `SearchTagTokenError`
    """

    def __init__(self, named_token: NamedToken) -> None:
        if named_token.category is not PostSearchTokenCategory.TAG:
            msg = f"A TagToken cannot be created from a NamedToken of type {named_token.category}. Only NamedTokens of type {PostSearchTokenCategory.TAG} are allowed"  # noqa: E501
            raise ValueError(msg)

        self.named_token = named_token
        self.has_wildcards: bool = bool(self.named_token.wildcard_positions)

        if self.has_wildcards:
            self.partial = named_token.arg_with_wildcards()
        else:
            self.partial = named_token.arg

        split = self.partial.split(TAG_CATEGORY_DELIMITER)
        if split:
            self.categories = split[:-1]
            self.name = split[-1]
        else:
            self.categories = []
            self.name = self.partial

        for category in self.categories:
            if "*" in category or "%" in category:
                msg = "Tag categories may not contain wildcards"
                raise SearchTagTokenError(msg)

    def get_post_filter_expr(self) -> Q:
        """Get a Post model filter expression for filtering Post results by a tag's
        name and categories. The query expression is intended to only return posts
        with tags where all the categories match, but the tag name is handled as a
        partial name or may contain wildcards.

        Note: categories may not contain wildcards, only tag name
        """

        if self.has_wildcards:
            expr = Q(tags__name__like=self.name)
        else:
            expr = Q(tags__name=self.name)

        # Tag categories expr(s)
        categories_search_dict = {}
        for i, category in enumerate(reversed(self.categories)):
            parent_str = "__parent"
            filter_str = f"tags__category{parent_str * i}__name"
            categories_search_dict[filter_str] = category

        return expr & Q(**categories_search_dict)

    def get_tag_filter_autocomplete_expr(self) -> Q:
        """Get a Tag model filter expression for filtering autocomplete results by a
        tag's name and categories treating `tag_str` as a potentially incomplete
        partial"""

        # Tag name expr
        if self.has_wildcards:
            expr = Q(name__like=self.name)
        else:
            expr = Q(name__icontains=self.name)

        # Tag categories expr(s)
        if self.categories:
            # Parsed categories, so check tag exactly matches the parent categories
            categories_search_dict = {}
            for i, category in enumerate(reversed(self.categories)):
                parent_str = "__parent"
                filter_str = f"category{parent_str * i}__name"
                categories_search_dict[filter_str] = category

            return expr & Q(**categories_search_dict)

        # No parsed categories, so check tag parent categories up to a maximum
        # of `MAX_TAG_CATEGORY_DEPTH` parents for matching names treating the
        # `tag_str` as a partial.
        categories_search_dict = {}
        for i in range(MAX_TAG_CATEGORY_DEPTH):
            parent_str = "__parent"
            filter_str = f"category{parent_str * i}__name__icontains"
            categories_search_dict[filter_str] = self.partial
            expr = expr | Q(**categories_search_dict)
        return expr


@dataclass
class NamedToken:
    """A parsed token for Post search

    Note that wildcards (*) are parsed out of the `arg` field into an array of
    index/positions. This facilitates validation of NamedTokens immediately
    after creation, since `arg` values can't allow the "*" character as part of the base
    value since it's reserved for wildcard usage. When the full arg with wildcards is
    needed it can simply be reconstructed from the `wildcard_positions`. This way
    the `NamedToken` initializes with a clean `arg` value.

    Attributes:
        category: TokenCategory
        name: str, the readable name of the NamedToken used in search queries to specify
            a particular token in search queries
        arg: str,  an argument value for filter tokens
        arg_relation_str: str, a character defining the relationship between the arg
            and its value e.g. an exact match (=), less than (<), or greater than (>).
        arg_relation: TokenArgRelation, the parsed version of `arg_relation_str` which
            is used for matching against an allowed set of search operators
        wildcard_positions: array[int], an array of wild positions from the original
            arg input
        negate: bool, Posts matching this token should NOT be returned
    """

    category: PostSearchTokenCategory
    name: str | StrOrPromise
    arg: str = ""
    arg_relation_str: str = TokenArgRelation.EQUAL.value
    arg_relation: TokenArgRelation | None = field(init=False)
    wildcard_positions: array[int] = field(init=False)
    negate: bool = False

    def __post_init__(self):
        self.arg_relation = (
            TokenArgRelation(self.arg_relation_str) if self.arg_relation_str else None
        )

        self.arg = self.arg.strip()
        wildcard_split = list(re.finditer(r"\*", self.arg))
        if len(wildcard_split) > 4:
            msg = "This token's argument has too many wildcards"
            raise ValidationError(msg)

        if len(wildcard_split) > 0:
            self.wildcard_positions = array(
                "I", [m.span()[0] for m in re.finditer(r"\*", self.arg)]
            )
        else:
            self.wildcard_positions = array("I", [])
        self.arg = self.arg.replace("*", "")

    @classmethod
    def from_token_string(cls, token: str) -> NamedToken | None:
        """Parses and validates a query token from a string.

        The `token` input should not contain any space characters.

        Args:
            token: str

        Raises: `ValidationError`
        """
        # Empty string
        if token == "":
            return None

        # Parse named tokens and simple tags
        token_name, *rest = FILTER_SPLIT_PATTERN.split(token, maxsplit=1)
        negate: bool = token_name[0] == "-"

        if negate:
            token_name = token_name[1:]

        if len(rest) == 0:
            # Anonymous token i.e. tag
            return NamedToken(
                PostSearchTokenCategory.TAG, token_name, token_name, negate=negate
            )

        if len(rest) == 1:
            msg = "An invalid query split occurred"
            raise ValidationError(msg)

        if len(rest) == 2:
            arg_relation = rest[0]
            token_arg = rest[1]

            if FILTER_SPLIT_PATTERN.search(token_arg):
                msg = "Search query filters may only have one operator"
                raise ValidationError(msg)
            try:
                # NamedToken filter with an argument
                token_category = PostSearchTokenCategory.select(token_name)
            except SearchTokenNameError as err:
                msg = f'The name "{token_name}" is not a valid filter'
                raise ValidationError(msg) from err
            else:
                if arg_relation not in [
                    x.value for x in token_category.value.allowed_arg_relations
                ]:
                    msg = f'The <span class="font-bold font-mono">{token_category.value.name}</span> filter does not accept the <span class="font-bold font-mono">{arg_relation}</span> operator'  # noqa: E501
                    raise ValidationError(msg)

            named_token = cls(
                token_category,
                name=token_name,
                arg=token_arg.replace(SEARCH_ARG_QUOTE, ""),
                arg_relation_str=arg_relation,
                negate=negate,
            )

            named_token.is_arg_valid()
            return named_token

        # Invalid token
        msg = f'The query token "{token}" is invalid'
        raise ValidationError(msg)

    def is_arg_valid(self):
        """Checks the validity of a Token's argument (arg) value

        Note: Most WildcardSearchToken(s) will use the same validator for the wildcard
        and non-wildcard variants, but some may need to provide a more permissive
        validator to allow for incomplete arguments (e.g. URLs) which is why the
        WildcardSearchToken may override the base `arg_validator` on an as-needed basis.

        Raises: `ValidationError`
        """
        if isinstance(self.category.value, WildcardSearchTokenCategory):
            validator = self.category.value.wildcard_arg_validator
        else:
            validator = self.category.value.arg_validator

        if validator and self.arg:
            validator(self.arg)

    def arg_with_wildcards(self):
        """Reconstructs original `arg` with Postgres compatible wildcards from the
        `wildcard_positions`"""

        arg = self.arg
        for pos in self.wildcard_positions:
            arg = arg[:pos] + "%" + arg[pos:]

        return arg


@dataclass
class AutocompleteItem:
    token_category: PostSearchTokenCategory
    name: str | StrOrPromise
    tag_category: TagCategory | None = None
    tag_id: int | None = None
    alias: str | StrOrPromise = ""
    extra: str | StrOrPromise = ""

    def get_tag_label(self) -> SafeString:
        """Build and return an AutocompleteItem's label to be used for rendering
        tag and their category chains"""
        if self.tag_category:
            categories = [self.tag_category]
            for _ in range(MAX_TAG_CATEGORY_DEPTH):
                if categories[-1].parent is None:
                    break
                categories.append(categories[-1].parent)

            return SafeString(
                TAG_CATEGORY_DELIMITER.join(
                    [cat.name for cat in reversed(categories)] + [self.name]
                )
            )

        return SafeString(self.name)

    def get_search_token_string(self) -> SafeString:
        """Build and return an a valid search token string for this AutocompleteItem"""
        if self.tag_category:
            categories = [self.tag_category]
            for _ in range(MAX_TAG_CATEGORY_DEPTH):
                if categories[-1].parent is None:
                    break
                categories.append(categories[-1].parent)

            return SafeString(
                TAG_CATEGORY_DELIMITER.join(
                    [cat.name for cat in reversed(categories)] + [self.name]
                )
            )

        return SafeString(self.name)

    def get_default_search_token_operator(self) -> SafeString:
        if len(self.token_category.value.allowed_arg_relations) > 0:
            return SafeString(self.token_category.value.allowed_arg_relations[0].value)
        return SafeString("")

    def is_tag_item(self) -> bool:
        return self.token_category in (
            PostSearchTokenCategory.TAG,
            PostSearchTokenCategory.TAG_ALIAS,
        )


class PostSearch:
    """Class to model a Post search query
    Models a post search query. Validates query arguments and retrieves autocompletion
    and post search results.

    Post search queries parse a space delimited string which is split into tokens
    corresponding to any of the values in the `TokenCategory` Enum.

    Tag categories may be searched by delimiting them with colons by default. For
    example a token of `Locations:Countries:Chile` has a top-level category of
    "Locations" a sub-category of "Countries" and a tag name of "Chile".

    Beyond simple tags, there are also many filtering options which are all delimited
    by a =, <, or > symbol. For example, a token of `uploaded_by=pablo` has a token
    category of "uploaded_by" with an argument of "pablo" which can be a user's
    username. Some filters may also include wildcards, so following the previous
    example, `uploaded_by=pablo*` would return any posts uploaded by a user with the
    username prefix of "pablo". Similarly, wildcards may appear at the beginning or in
    the middle of the argument. Such as, `uploaded_by=*pablo` or `uploaded_by=pa*blo`.

    All tags and filters may be prefixed with a "-" sign to indicate the search for that
    token should be inverted. For example a token of `-uploaded_by=pablo` would exclude
    any posts uploaded by the user "pablo" in the results.
    """

    def __init__(
        self,
        query: str | QueryDict,
        *,
        exclude_tags: QuerySet[Tag] | None = None,
        max_tags: int = 20,
        max_aliases: int = 20,
    ):
        self.query = query
        self.max_tags = max_tags
        self.max_aliases = max_aliases
        self.exclude_tags = exclude_tags
        self.partial: str = ""
        if isinstance(self.query, QueryDict):
            self.tokens = self.parse_querydict(self.query)
        elif isinstance(self.query, str):
            query_split = re.split(r"\s+", self.query)
            if len(query_split) > 0:
                self.partial = query_split[-1]

            self.tokens: list[NamedToken] = self.parse_query(self.query)

    @staticmethod
    def parse_querydict(querydict: QueryDict) -> list[NamedToken]:
        """Parses a post search query submitted via form instead of a query string.

        Each parameter should match an existing `TokenCategory` with the exception of
        tags which are submitted as a list of tag IDs in the `tagset` parameter.

        Raises: `ValidationError`
        """

        parsed_tokens: list[NamedToken] = []

        # Parse tag tokens
        tagset = querydict.getlist("tagset")
        for tag_id in tagset:
            tag_token = NamedToken(
                PostSearchTokenCategory.TAG_ID,
                PostSearchTokenCategory.TAG_ID.value.name,
                tag_id,
            )

            tag_token.is_arg_valid()
            parsed_tokens.append(tag_token)

        # Parse other tokens
        for key, value in querydict.items():
            try:
                token_category = PostSearchTokenCategory.select(key)

                arg_relation = querydict.get(
                    f"{key}_relation", token_category.value.allowed_arg_relations[0]
                )

                if arg_relation not in [
                    x.value for x in token_category.value.allowed_arg_relations
                ]:
                    msg = f'The {token_category.value.name} filter does not accept the "{arg_relation}" operator'  # noqa: E501
                    raise ValidationError(msg)

                negate = bool(querydict.get(f"{key}_negate", False))

                named_token = NamedToken(
                    token_category,
                    name=key,
                    arg=str(value),
                    arg_relation_str=str(arg_relation),
                    negate=negate,
                )

                named_token.is_arg_valid()
                parsed_tokens.append(named_token)

            except SearchTokenNameError:
                # Bad tokens are ignored
                pass

        return parsed_tokens

    @staticmethod
    def parse_query(query: str) -> list[NamedToken]:
        """Parses a post search query into named tokens.

        Arguments:
            query: str, a query string containing space-delimited search tokens

        Raises:
            `ValidationError`
        """
        if query == "":
            return []

        parsed_tokens: list[NamedToken] = []
        quote_matches = list(re.finditer(SEARCH_ARG_QUOTE_PATTERN, query))
        if len(quote_matches) > 0:
            if len(quote_matches) % 2 == 1:
                raise UnevenArgumentQuotesError

            tokens: list[str] = []
            prev_span_end = 0
            for i in range(0, len(quote_matches), 2):
                quote_match = quote_matches[i]
                next_quote_match = quote_matches[i + 1]
                tokens.extend(
                    re.split(
                        TOKEN_SPLIT_PATTERN,
                        query[prev_span_end : quote_match.start()],
                    )
                )

                # Append quote span to last parsed token
                tokens[-1] += query[quote_match.end() : next_quote_match.start()]
                prev_span_end = next_quote_match.end()

            # Parse tokens in final span of query
            tokens.extend(re.split(TOKEN_SPLIT_PATTERN, query[prev_span_end:]))
        else:
            tokens = re.split(r"\s+", query)

        for token in tokens:
            if named_token := NamedToken.from_token_string(token):
                named_token.is_arg_valid()
                parsed_tokens.append(named_token)

        return parsed_tokens

    def get_search_conditions(self) -> list[Q] | None:  # noqa: C901, PLR0912, PLR0915
        """Builds a Post filter expression based on the provided `tokens`

        Note: tokens are validated when parsing the query string, so
        all token arguments are assumed to be safe here.

        Args:
            tokens: parsed tokens from a query string

        Raises:
            InvalidMimetypeError
            InvalidRatingLabelError
            UnsupportedSearchOperatorError
        """
        if self.exclude_tags is not None:
            search_conditions = [~Q(tags__in=self.exclude_tags)]
        else:
            search_conditions: list[Q] = []
        for token in self.tokens:
            match token.category:
                case PostSearchTokenCategory.TAG:
                    tag_token = TagToken(token)
                    token_expr = tag_token.get_post_filter_expr()

                case PostSearchTokenCategory.TAG_ALIAS:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            if token.wildcard_positions:
                                token_expr = Q(
                                    tags__tagalias__name__like=token.arg_with_wildcards()
                                )
                            else:
                                token_expr = Q(tags__tagalias__name=token.arg)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )

                case PostSearchTokenCategory.TAG_ID:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(tags__pk=int(token.arg))
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.POST_ID:
                    match token.arg_relation:
                        case TokenArgRelation.LESS_THAN:
                            token_expr = Q(pk__lt=token.arg)
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(pk=token.arg)
                        case TokenArgRelation.GREATER_THAN:
                            token_expr = Q(pk__gt=token.arg)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.COMMENT_COUNT:
                    match token.arg_relation:
                        case TokenArgRelation.LESS_THAN:
                            token_expr = Q(comment_count__lt=token.arg)
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(comment_count=token.arg)
                        case TokenArgRelation.GREATER_THAN:
                            token_expr = Q(comment_count__gt=token.arg)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.COMMENT_BY:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            if token.wildcard_positions:
                                token_expr = Q(
                                    comment__user__username__like=token.arg_with_wildcards()
                                )
                            else:
                                token_expr = Q(comment__user__username=token.arg)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.FAV_COUNT:
                    match token.arg_relation:
                        case TokenArgRelation.LESS_THAN:
                            token_expr = Q(fav_count__lt=int(token.arg))
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(fav_count=int(token.arg))
                        case TokenArgRelation.GREATER_THAN:
                            token_expr = Q(fav_count__gt=int(token.arg))
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.TAG_COUNT:
                    match token.arg_relation:
                        case TokenArgRelation.LESS_THAN:
                            token_expr = Q(tag_count__lt=int(token.arg))
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(tag_count=int(token.arg))
                        case TokenArgRelation.GREATER_THAN:
                            token_expr = Q(tag_count__gt=int(token.arg))
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.RATING_NUM:
                    match token.arg_relation:
                        case TokenArgRelation.LESS_THAN:
                            token_expr = Q(rating_level__lt=int(token.arg))
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(rating_level=int(token.arg))
                        case TokenArgRelation.GREATER_THAN:
                            token_expr = Q(rating_level__gt=int(token.arg))
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.RATING_LABEL:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            rating = RatingLevel.select(token.arg)
                            if rating is None:
                                raise InvalidRatingLabelError
                            token_expr = Q(rating_level=rating.value)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.SOURCE:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            if token.wildcard_positions:
                                token_expr = Q(src_url__like=token.arg_with_wildcards())
                            else:
                                token_expr = Q(src_url=token.arg)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.POSTED_BY:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            if token.wildcard_positions:
                                token_expr = Q(
                                    uploader__username__like=token.arg_with_wildcards()
                                )
                            else:
                                token_expr = Q(uploader__username=token.arg)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.POSTED_ON:
                    match token.arg_relation:
                        # TODO: handle arg with valid date format but invalid date value
                        #     e.g. 2025-02-31
                        case TokenArgRelation.LESS_THAN:
                            token_expr = Q(post_date__lt=token.arg)
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(post_date=token.arg)
                        case TokenArgRelation.GREATER_THAN:
                            token_expr = Q(post_date__gt=token.arg)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.HEIGHT:
                    match token.arg_relation:
                        case TokenArgRelation.LESS_THAN:
                            token_expr = Q(image__height__lt=int(token.arg))
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(image__height=int(token.arg))
                        case TokenArgRelation.GREATER_THAN:
                            token_expr = Q(image__height__gt=int(token.arg))
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.WIDTH:
                    match token.arg_relation:
                        case TokenArgRelation.LESS_THAN:
                            token_expr = Q(image__width__lt=int(token.arg))
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(image__width=int(token.arg))
                        case TokenArgRelation.GREATER_THAN:
                            token_expr = Q(image__width__gt=int(token.arg))
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.MIMETYPE:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            smt = SupportedMediaType.select_by_mime(token.arg)
                            if smt is None:
                                raise InvalidMimetypeError
                            token_expr = Q(type=smt.name)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.FILE_EXTENSION:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            smt = SupportedMediaType.select_by_ext(token.arg)
                            if smt is None:
                                raise InvalidMimetypeError
                            token_expr = Q(type=smt.name)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.COLLECTION_ID:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(collection=int(token.arg))
                        case TokenArgRelation.LESS_THAN:
                            token_expr = Q(collection__lt=int(token.arg))
                        case TokenArgRelation.GREATER_THAN:
                            token_expr = Q(collection__gt=int(token.arg))
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.COLLECTION:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            if token.arg.casefold() == SearchBoolean.NO.value:
                                token_expr = Q(collection=None)
                            else:
                                token_expr = ~Q(collection=None)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.COLLECTION_NAME:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            if token.wildcard_positions:
                                token_expr = Q(
                                    collection__name__like=token.arg_with_wildcards()
                                )
                            else:
                                token_expr = Q(collection__name=token.arg)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.PARENT:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            if token.arg.casefold() == SearchBoolean.NO.value:
                                token_expr = Q(parent=None)
                            else:
                                token_expr = ~Q(parent=None)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.PARENT_ID:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(parent__pk=int(token.arg))
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.CHILD:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            if token.arg.casefold() == SearchBoolean.NO.value:
                                token_expr = Q(child_post_ids=None)
                            else:
                                token_expr = ~Q(child_post_ids=None)
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case PostSearchTokenCategory.CHILD_ID:
                    match token.arg_relation:
                        case TokenArgRelation.EQUAL:
                            token_expr = Q(child_post_ids__contains=[token.arg])
                        case _:
                            raise UnsupportedSearchOperatorError(
                                token.arg_relation_str, token
                            )
                case _:
                    raise SearchTokenFilterNotImplementedError(token.category.value)

            if token.negate:
                token_expr = ~token_expr

            search_conditions.append(token_expr)

        return search_conditions

    def get_posts(self) -> PostQuerySet:
        token_categories = [x.category for x in self.tokens]
        posts = Post.posts.all()
        if PostSearchTokenCategory.COMMENT_COUNT in token_categories:
            posts = posts.annotate_comment_count()
        if PostSearchTokenCategory.FAV_COUNT in token_categories:
            posts = posts.annotate_fav_count()
        if PostSearchTokenCategory.TAG_COUNT in token_categories:
            posts = posts.annotate_tag_count()
        if (
            PostSearchTokenCategory.CHILD in token_categories
            or PostSearchTokenCategory.CHILD_ID in token_categories
        ):
            posts = posts.annotate_child_posts()
        if search_conditions := self.get_search_conditions():
            for condition in search_conditions:
                posts = posts.filter(condition)
            return posts.distinct()
        return posts

    def autocomplete(
        self,
        partial: str | None = None,
        exclude_tags: QuerySet[Tag] | None = None,
        user: User | None = None,
        *,
        show_filters: bool = True,
    ) -> chain[AutocompleteItem]:
        """Return autocomplete matches based on the existing search query and
        the provided `partial`"""
        if partial is None:
            partial = self.partial

        # Trim "-" from negated partial
        if len(partial) > 0 and partial[0] == "-":
            partial = partial[1:]

        # Don't yield autocompletion for duplicate filter or tag
        if len(list(filter(lambda tok: tok.name == partial, self.tokens))) > 1:
            tag_token_names = [
                str(tok.name)
                for tok in self.tokens
                if tok.category is PostSearchTokenCategory.TAG
            ]
        else:
            tag_token_names = [
                str(tok.name)
                for tok in self.tokens
                # Yield autocomplete item if name matches partial exactly
                if tok.category is PostSearchTokenCategory.TAG and tok.name != partial
            ]

        if user:
            tag_autocompletions = autocomplete_tags(
                Tag.tags.for_user(user),
                partial,
                exclude_tag_names=tag_token_names,
            )
            tag_alias_autocompletions = autocomplete_tag_aliases(
                TagAlias.aliases.for_user(user),
                partial,
                exclude_alias_names=tag_token_names,
            )
        else:
            tag_autocompletions = autocomplete_tags(
                Tag.tags.all(),
                partial,
                exclude_tag_names=tag_token_names,
            )

            tag_alias_autocompletions = autocomplete_tag_aliases(
                TagAlias.aliases.all(), partial, exclude_alias_names=tag_token_names
            )

        tag_autocompletions = take(self.max_tags, tag_autocompletions)
        tag_alias_autocompletions = take(self.max_aliases, tag_alias_autocompletions)
        autocomplete_items = chain(tag_autocompletions, tag_alias_autocompletions)

        matching_items_by_name = (
            AutocompleteItem(category, category.value.name)
            for category in PostSearchTokenCategory
            if partial in category.value.name
        )

        matching_items_by_alias = chain(
            *[
                [
                    AutocompleteItem(category, category.value.name, alias=alias)
                    for alias in category.value.aliases
                    if partial in alias
                ]
                for category in PostSearchTokenCategory
            ]
        )

        if show_filters:
            # Add search filters to autocomplete items
            autocomplete_items = chain(
                matching_items_by_name,
                matching_items_by_alias,
                autocomplete_items,
            )

        return autocomplete_items
