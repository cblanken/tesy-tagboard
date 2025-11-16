from dataclasses import dataclass
from enum import Enum
from enum import StrEnum
from typing import Self

from django.utils.deconstruct import deconstructible


@dataclass
@deconstructible
class TagCategoryData:
    """Class for categorizes tags"""

    shortcode: str
    prefixes: set[str]
    display_name: str

    def __repr__(self):
        return f"<TagCategory: {self.shortcode} - {','.join(self.prefixes)}>"

    def __eq__(self, other):
        return (
            self.shortcode == other.shortcode
            and self.prefixes == other.prefixes
            and self.display_name == other.display_name
        )

    def __hash__(self):
        return hash(self.shortcode)


class TagCategory(Enum):
    """A basic tag with no prefix"""

    BASIC = TagCategoryData("BA", {"", "basic"}, "basic")
    ARTIST = TagCategoryData("AR", {"art", "artist"}, "artist")
    COPYRIGHT = TagCategoryData("CO", {"copy", "copyright"}, "copyright")

    @classmethod
    def select(cls, name: str):
        """Select TagCategory by name or one of its aliases"""
        for names, category in [(x.value.prefixes, x) for x in TagCategory]:
            if name in names:
                return category

        return cls.BASIC


class MediaCategory(StrEnum):
    """MIME media content type"""

    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"


@dataclass
class MediaType:
    """A class describing the content type of some media following
    the MIME data convention
    desc: a string describing the MediaType
    extensions: a list of valid file extension for the MediaType
    category: a MediaCategory (AUDIO, IMAGE, or VIDEO)
    subtype: a Media's subtype (e.g. 'svg' in image/svg, or 'png' in image/png)
    suffix: an optional suffix to the MediaType definition (e.g. 'xml' in image/svg+xml)
    """

    desc: str
    extensions: list[str]
    category: MediaCategory
    subtype: str
    suffix: str = ""

    def get_template(self):
        template = f"{self.category.value}/{self.subtype}"
        if self.suffix:
            template += f"+{self.suffix}"
        return template


class SupportedMediaTypes(Enum):
    # Image types
    AVIF = MediaType("AVIF image", ["avif"], MediaCategory.IMAGE, "avif")
    BMP = MediaType("Windows Bitmap Graphics", ["bmp"], MediaCategory.IMAGE, "bmp")
    GIF = MediaType("GIF", ["gif"], MediaCategory.IMAGE, "gif")
    JPEG = MediaType("JPEG image", ["jpg", "jpeg"], MediaCategory.IMAGE, "jpeg")
    PNG = MediaType("PNG", ["png"], MediaCategory.IMAGE, "png")
    WEBP = MediaType("WEBP image", ["webp"], MediaCategory.IMAGE, "webp")
    # TODO: support SVG

    # Audio types
    MP3 = MediaType("MP3 audio", ["mp3", "mpeg"], MediaCategory.AUDIO, "mpeg")
    WAV = MediaType("WAV audio", ["wav"], MediaCategory.AUDIO, "wav")

    # Video types
    MP4 = MediaType("MP4 video", ["mp4"], MediaCategory.VIDEO, "mp4")
    MPEG = MediaType("MPEG video", ["mpeg"], MediaCategory.VIDEO, "mpeg")
    WEBM = MediaType("WEBM video", ["webm"], MediaCategory.VIDEO, "webm")

    @classmethod
    def find(cls, template: str) -> Self | None:
        """A function to search the supported media types by
        template string.
        Returns the first matched instance of SupportedMediaTypes"""
        for smt in cls.__members__.values():
            if template == smt.value.get_template():
                return smt

        return None
