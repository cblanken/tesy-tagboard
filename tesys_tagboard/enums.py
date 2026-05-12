from dataclasses import dataclass
from enum import Enum
from enum import StrEnum
from typing import Self

from django.db.models import IntegerChoices
from django.utils.translation import gettext_lazy as _


class SearchBoolean(Enum):
    # Translators: search parameter confirmation
    YES = _("yes")
    # Translators: search parameter negation
    NO = _("no")


class RatingLevel(IntegerChoices):
    """Rating levels for posts
    Default: UNRATED

    These levels are ordered such that SAFE < UNRATED < QUESTIONABLE < EXPLICIT
    This enables a simple integer comparison to be made on the RatingLevel value
    to show only the desired posts
    """

    SAFE = 0, _("Safe")
    UNRATED = 1, _("Unrated")
    QUESTIONABLE = 50, _("Questionable")
    EXPLICIT = 100, _("Explicit")

    @classmethod
    def select(cls, label: str) -> Self | None:
        """Select rating level by label

        Lettercase is ignored
        """
        label = label.strip()
        selected_ratings = [r for r in cls if r.label.lower() == label.lower()]
        if len(selected_ratings) == 0:
            msg = f'Not match for rating level called "{label}"'
            raise ValueError(msg)
        return selected_ratings[0]


class MediaCategory(StrEnum):
    """MIME media content type"""

    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"


@dataclass
class MediaType:
    """A class describing the content type of some media following
    the MIME data convention

    Args:
        desc: str = describing the MediaType
        extensions: list[str] = a list of valid file extension for the MediaType
        category: MediaCategory = MediaCategory.(AUDIO, IMAGE, or VIDEO)
        subtype: str  = the subtype (e.g. 'png' in image/png) in the MIME definition
        suffix: str = an optional suffix to the MediaType definition (e.g. 'xml' in the
            MIME type 'image/svg+xml')
    """

    desc: str
    extensions: list[str]
    category: MediaCategory
    subtype: str
    suffix: str = ""

    def get_mimetype(self):
        template = f"{self.category.value}/{self.subtype}"
        if self.suffix:
            template += f"+{self.suffix}"
        return template


class SupportedMediaType(Enum):
    # Image types
    AVIF = MediaType("AVIF image", ["avif"], MediaCategory.IMAGE, "avif")
    BMP = MediaType("Windows Bitmap Graphics", ["bmp"], MediaCategory.IMAGE, "bmp")
    GIF = MediaType("GIF", ["gif"], MediaCategory.IMAGE, "gif")
    JPEG = MediaType("JPEG image", ["jpg", "jpeg"], MediaCategory.IMAGE, "jpeg")
    PNG = MediaType("PNG", ["png"], MediaCategory.IMAGE, "png")
    WEBP = MediaType("WEBP image", ["webp"], MediaCategory.IMAGE, "webp")
    TIFF = MediaType("TIFF image", ["tif", "tiff"], MediaCategory.IMAGE, "tiff")
    # TODO: support SVG

    # Audio types
    MP3 = MediaType("MP3 audio", ["mp3", "mpeg"], MediaCategory.AUDIO, "mpeg")
    WAV = MediaType("WAV audio", ["wav"], MediaCategory.AUDIO, "vnd.wav")
    WAV2 = MediaType("WAV audio", ["wav"], MediaCategory.AUDIO, "vnd.wave")
    WAV3 = MediaType("WAV audio", ["wav"], MediaCategory.AUDIO, "wave")
    WAV4 = MediaType("WAV audio", ["wav"], MediaCategory.AUDIO, "x-wav")

    # Video types
    MP4 = MediaType("MP4 video", ["mp4"], MediaCategory.VIDEO, "mp4")
    MPEG = MediaType("MPEG video", ["mpeg"], MediaCategory.VIDEO, "mpeg")
    WEBM = MediaType("WEBM video", ["webm"], MediaCategory.VIDEO, "webm")

    @classmethod
    def select_by_mime(cls, template: str) -> Self | None:
        """A function to select the supported media type by the given MIME type template
        string. Returns the first matched instance of SupportedMediaTypes"""
        for smt in cls:
            if template == smt.value.get_mimetype():
                return smt

        return None

    @classmethod
    def select_by_ext(cls, template: str) -> Self | None:
        """A function to select the supported media type matching the given extension.
        Returns the first matched instance of SupportedMediaTypes"""
        for smt in cls:
            if template in smt.value.extensions:
                return smt

        return None


class TokenArgRelation(Enum):
    """Enum for all valid token arg delimiters and used to decide how a
    token's argument should be interpreted"""

    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
