from itertools import chain

from django.conf import settings
from django.core import validators
from django.core.exceptions import ValidationError
from django.utils.regex_helper import _lazy_re_compile
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from .enums import RatingLevel
from .enums import SearchBoolean
from .enums import SupportedMediaType
from .upload import fix_upload_content_type

rgb_validator = validators.RegexValidator(r"^#[0-9A-F]{6}$")
md5_validator = validators.RegexValidator(r"^[0-9A-Z]{32}$")
phash_validator = validators.RegexValidator(r"^[0-9a-z]{16}$")
dhash_validator = validators.RegexValidator(r"^[0-9a-z]{16}$")
tag_name_validator = validators.RegexValidator(
    _lazy_re_compile(r"^[a-zA-Z\d\:-_]+$"), message=_("Enter a valid tag name.")
)

tag_token_validator = validators.RegexValidator(
    _lazy_re_compile(r"^[a-zA-Z\d\:-_" + settings.TAG_CATEGORY_DELIMITER + "]+$"),
    message=_("Enter a valid tag token."),
)
tagset_name_validator = validators.RegexValidator(r"^[a-z\d\-_]+$")
username_validator = validators.RegexValidator(
    _lazy_re_compile(r"^[a-zA-Z\d_\-]+\Z"),
    message=_("Enter a valid username."),
)
positive_int_validator = validators.RegexValidator(
    _lazy_re_compile(r"^\d+$"),
    message=_("Enter a positive integer."),
)
wildcard_url_validator = validators.RegexValidator(
    # For allowing URLs with wildcards and without requiring
    # a protocol specifier or other URL validation
    r"[ A-Za-z0-9-.,_~:\/#@!$&';%=\*\+\(\)\?\[\]]",
    message=_("Enter a valid URL with wildcards"),
)
iso_date_validator = validators.RegexValidator(
    _lazy_re_compile(
        r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?:\:\d{2})?(?:\+\d{2}:\d{2})?)?$"
    ),
    message=_(
        "Enter a date in the following format: <span class='font-bold font-mono'>"
        "YYYY-MM-DD</span>"
    ),
)


def yes_no_validator(arg: str):
    if arg not in [x.value for x in SearchBoolean]:
        msg = format_lazy(
            _("Enter {yes} or {no}"),
            yes=SearchBoolean.YES.value,
            no=SearchBoolean.NO.value,
        )
        raise ValidationError(msg)


collection_name_validator = validators.RegexValidator(
    _lazy_re_compile(r"^[a-zA-Z\d_\- ]+\Z"),
    message=_("Enter a valid collection name."),
)
wildcard_collection_name_validator = validators.RegexValidator(
    _lazy_re_compile(r"^[a-zA-Z\d_\-\.\s]+\Z"),
    message=_("Enter a valid collection name with wildcards."),
)


def mimetype_validator(mimetype: str):
    mimetypes = [smt.value.get_mimetype() for smt in SupportedMediaType]
    if not SupportedMediaType.select_by_mime(mimetype):
        msg = _(
            "The MIME type argument must match one of the supported MIME types: %s"
        ) % ", ".join(
            [f"<span class='font-mono font-bold'>{mt}</span>" for mt in mimetypes]
        )
        raise ValidationError(msg)


def file_extension_validator(ext: str):
    extensions = sorted(
        set(chain(*[smt.value.extensions for smt in SupportedMediaType]))
    )
    if ext not in extensions:
        msg = _(
            "The file extension argument must match a supported file extension: %s"
        ) % ", ".join(extensions)
        raise ValidationError(msg)


def tagset_validator(tag_ids: list):
    """Validates a tagset. A Sequence of positive integers."""
    msg = _("A tagset may only contain positive integers")
    try:
        for tag_id in tag_ids:
            if int(tag_id) < 0:
                raise ValidationError(msg)

    except (ValueError, TypeError) as e:
        raise ValidationError(msg) from e


def media_file_supported_validator(file):
    try:
        fix_upload_content_type(file)
    except UnicodeDecodeError as err:
        msg = f"Could not read file because of a decoding error: {err}"
        raise ValidationError(msg) from err
    if not SupportedMediaType.select_by_mime(file.content_type):
        msg = f"File with a content type of {file.content_type} is not supported"
        raise ValidationError(msg)


def media_file_type_matches_ext_validator(file):
    # TODO
    return


def rating_label_validator(value: str):
    value = value.lower()
    rating_labels = [x.name.lower() for x in RatingLevel]
    if value not in rating_labels:
        label_names = ", ".join(rating_labels)
        msg = f"Rating label must be one of: {label_names}"
        raise ValidationError(msg)


def rating_level_validator(value):
    rating_levels = [x.value for x in RatingLevel]
    if value not in rating_levels:
        msg = f"Rating levels must be one of {rating_levels}"
        raise ValidationError(msg)
