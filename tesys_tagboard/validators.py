from itertools import chain

from django.conf import settings
from django.core import validators
from django.core.exceptions import ValidationError
from django.utils.regex_helper import _lazy_re_compile
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from .enums import RatingLevel, SearchBoolean, SupportedMediaType
from .upload import fix_upload_content_type

validate_rgb = validators.RegexValidator(r"^#[0-9A-F]{6}$")
validate_md5 = validators.RegexValidator(r"^[0-9A-Z]{32}$")
validate_phash = validators.RegexValidator(r"^[0-9a-z]{16}$")
validate_dhash = validators.RegexValidator(r"^[0-9a-z]{16}$")
validate_tag_name = validators.RegexValidator(
    _lazy_re_compile(r"^[a-zA-Z\d\:-_]+$"), message=_("Enter a valid tag name.")
)

validate_tag_token = validators.RegexValidator(
    _lazy_re_compile(r"^[a-zA-Z\d\:-_" + settings.TAG_CATEGORY_DELIMITER + "]+$"),
    message=_("Enter a valid tag token."),
)
validate_tagset_name = validators.RegexValidator(r"^[a-z\d\-_]+$")
validate_username = validators.RegexValidator(
    _lazy_re_compile(r"^[a-zA-Z\d_\-]+\Z"),
    message=_("Enter a valid username."),
)
validate_positive_int = validators.RegexValidator(
    _lazy_re_compile(r"^\d+$"),
    message=_("Enter a positive integer."),
)
validate_wildcard_url = validators.RegexValidator(
    # For allowing URLs with wildcards and without requiring
    # a protocol specifier or other URL validation
    r"[ A-Za-z0-9-.,_~:\/#@!$&';%=\*\+\(\)\?\[\]]",
    message=_("Enter a valid URL with wildcards"),
)
validate_iso_date = validators.RegexValidator(
    _lazy_re_compile(
        r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?:\:\d{2})?(?:\+\d{2}:\d{2})?)?$"
    ),
    message=_(
        "Enter a date in the following format: <span class='font-bold font-mono'>"
        "YYYY-MM-DD</span>"
    ),
)


def validate_yes_no(arg: str):
    if arg not in [x.value for x in SearchBoolean]:
        msg = format_lazy(
            _("Enter {yes} or {no}"),
            yes=SearchBoolean.YES.value,
            no=SearchBoolean.NO.value,
        )
        raise ValidationError(msg)


validate_collection_name = validators.RegexValidator(
    _lazy_re_compile(r"^[a-zA-Z\d_\- ]+\Z"),
    message=_("Enter a valid collection name."),
)
validate_wildcard_collection_name = validators.RegexValidator(
    _lazy_re_compile(r"^[a-zA-Z\d_\-\.\s]+\Z"),
    message=_("Enter a valid collection name with wildcards."),
)


def validate_mimetype(mimetype: str):
    mimetypes = [smt.value.get_mimetype() for smt in SupportedMediaType]
    if not SupportedMediaType.select_by_mime(mimetype):
        msg = _(
            "The MIME type argument must match one of the supported MIME types: %s"
        ) % ", ".join(
            [f"<span class='font-mono font-bold'>{mt}</span>" for mt in mimetypes]
        )
        raise ValidationError(msg)


def validate_file_extension(ext: str):
    extensions = sorted(
        set(chain(*[smt.value.extensions for smt in SupportedMediaType]))
    )
    if ext not in extensions:
        msg = _(
            "The file extension argument must match a supported file extension: %s"
        ) % ", ".join(extensions)
        raise ValidationError(msg)


def validate_tagset(tag_ids: list):
    """Validates a tagset. A Sequence of positive integers."""
    msg = _("A tagset may only contain positive integers")
    try:
        for tag_id in tag_ids:
            if int(tag_id) < 0:
                raise ValidationError(msg)

    except (ValueError, TypeError) as e:
        raise ValidationError(msg) from e


def validate_supported_media_file(file):
    try:
        fix_upload_content_type(file)
    except UnicodeDecodeError as err:
        msg = f"Could not read file because of a decoding error: {err}"
        raise ValidationError(msg) from err
    if not SupportedMediaType.select_by_mime(file.content_type):
        msg = f"File with a content type of {file.content_type} is not supported"
        raise ValidationError(msg)


def validate_media_file_type_matches_ext(file):
    # TODO
    return


def validate_rating_label(value: str):
    value = value.lower()
    rating_labels = [x.name.lower() for x in RatingLevel]
    if value not in rating_labels:
        label_names = ", ".join(rating_labels)
        msg = f"Rating label must be one of: {label_names}"
        raise ValidationError(msg)


def validate_rating_level(value):
    rating_levels = [x.value for x in RatingLevel]
    if value not in rating_levels:
        msg = f"Rating levels must be one of {rating_levels}"
        raise ValidationError(msg)
