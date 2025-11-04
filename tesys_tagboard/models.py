"""Models for Tesys's Tagboard"""

import uuid

from django.core import validators
from django.db import models
from django.utils.translation import gettext_lazy as _

from config.settings.base import AUTH_USER_MODEL


class TagCategory(models.Model):
    """Categories of Tags"""

    class Category(models.TextChoices):
        """A basic tag with no prefix"""

        BASIC = "BA", _("basic")
        ARTIST = "AT", _("artist")
        COPYRIGHT = "CP", _("copyright")
        RATING = "RT", _("rating")

    category = models.CharField(max_length=2, choices=Category.choices)
    prefix = models.CharField(max_length=24, default="")

    class Meta:
        verbose_name_plural = "tag categories"

    def __str__(self) -> str:
        return f"<TagCategory - {self.category}, prefix: {self.prefix}>"


class Tag(models.Model):
    """Tags for Media objects"""

    name = models.CharField(max_length=100)
    category = models.ForeignKey(TagCategory, on_delete=models.PROTECT)

    """Rating levels to filter content
    This field allows any tag to apply a rating
    """
    rating_level = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"<Tag - {self.name}, category: {self.category}>"


class TagAlias(models.Model):
    """Aliases for Tags"""

    name = models.CharField(max_length=100, unique=True)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"<TagAlias - {self.name}, tag: {self.tag}>"


class Artist(models.Model):
    """Model for Artists to identify all artwork from a particular source"""

    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, primary_key=True)
    bio = models.TextField()
    user = models.ForeignKey(AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    def __str__(self) -> str:
        return f"<Artist - {self.tag}, bio: {self.bio}>"


class MediaType(models.Model):
    """Media types supported for uploaded media
    See https://www.iana.org/assignments/media-types/media-types.xhtml
    for details
    """

    name = models.TextField(unique=True)
    template = models.TextField()
    desc = models.TextField(default="")

    # TODO validate templates support only audio, image, and video media

    def __str__(self) -> str:
        return (
            f"<MediaType - name: {self.name}, template: {self.template}, "
            f"desc: {self.desc}>"
        )


def unique_filename(instance, filename: str) -> str:
    """Generate a unique (UUID) filename"""
    filename_split = filename.split(".")
    new_name = uuid.uuid4()
    if len(filename_split) > 1:
        extension = filename_split[-1]
        return f"{new_name}.{extension}"
    return f"{new_name}"


class Media(models.Model):
    """Media linked to static files such as images, videos, or audio clips
    including file metadata
    """

    file = models.FileField(upload_to=unique_filename)
    og_name = models.TextField()
    type = models.ForeignKey(MediaType, on_delete=models.CASCADE)
    upload_date = models.DateTimeField(auto_now=True)
    edit_date = models.DateTimeField()
    size = models.BigIntegerField()
    source = models.URLField(max_length=255)

    md5 = models.CharField(
        unique=True,
        validators=[
            validators.RegexValidator(r"^[0-9A-Z]{32}$"),
        ],
    )

    """Perceptual (DCT) hash"""
    phash = models.CharField(
        unique=True,
        validators=[
            validators.RegexValidator(r"^[0-9a-z]{16}$"),
        ],
    )

    """Difference hash"""
    dhash = models.CharField(
        unique=True,
        validators=[
            validators.RegexValidator(r"^[0-9a-z]{16}$"),
        ],
    )

    # TODO: add duplicate detection
    # See https://github.com/JohannesBuchner/imagehash/issues/127 for
    # index recs for hashes

    class Meta:
        verbose_name_plural = "media"

    def __str__(self) -> str:
        return f"<Media - {self.file}, og_file: {self.og_name}, size: {self.source}>"


class Post(models.Model):
    """Posts made by users with attached media and meta data"""

    uploader = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    media = models.ForeignKey(Media, on_delete=models.CASCADE)
    post_date = models.DateTimeField(auto_now=True)
    tags = models.ManyToManyField(Tag)

    def __str__(self) -> str:
        return f"<Post - uploader: {self.uploader.name}, media: {self.media.file}, \
posted: {self.post_date}>"


class Pool(models.Model):
    """Collections of posts saved by users"""

    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    desc = models.TextField(max_length=1024)
    posts = models.ManyToManyField(Post)

    def __str__(self) -> str:
        return f"<Pool - name: {self.name}, user: {self.user}, desc: {self.desc}>"


class Comment(models.Model):
    """User comments"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    user = models.ForeignKey(AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    text = models.TextField(editable=True, max_length=500)

    def __str__(self) -> str:
        return f'<Comment: user: {self.user}, text: "{self.text}">'


class Favorite(models.Model):
    """Favorited posts by users"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return f"<Favorite - post: {self.post}, user: {self.user}>"
