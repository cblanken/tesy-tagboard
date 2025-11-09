"""Models for Tesys's Tagboard"""

import uuid
from hashlib import md5

import imagehash
from django.db import models
from django.db.models import Q
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from PIL import Image as PIL_Image

from config.settings.base import AUTH_USER_MODEL

from .validators import valid_dhash
from .validators import valid_md5
from .validators import valid_phash


class TagCategory(models.Model):
    """Categories of Tags"""

    class Category(models.TextChoices):
        """A basic tag with no prefix"""

        BASIC = "BA", _("basic")
        ARTIST = "AT", _("artist")
        COPYRIGHT = "CP", _("copyright")
        RATING = "RT", _("rating")

    category = models.CharField(max_length=2, choices=Category.choices)
    prefix = models.CharField(max_length=24, unique=True)

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
        constraints = [
            models.UniqueConstraint(
                fields=["name", "category"], name="unique_tag_name_cat"
            ),
        ]

    def __str__(self) -> str:
        return f"<Tag - {self.name}, category: {self.category}>"


class TagAlias(models.Model):
    """Aliases for Tags"""

    name = models.CharField(max_length=100, unique=True)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "tag"], name="unique_tagalias_name_tag"
            ),
        ]

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
    template = models.TextField(primary_key=True)
    desc = models.TextField(default="")

    # TODO validate templates support only audio, image, and video media

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(template__startswith="image/")
                    | Q(template__startswith="audio/")
                    | Q(template__startswith="video/")
                ),
                name="media_valid_mime_category",
            )
        ]

    def __str__(self) -> str:
        return f"<MediaType - name: {self.name}, template: {self.template}"


def unique_filename(instance, filename: str) -> str:
    """Generate a unique (UUID) filename"""
    filename_split = filename.split(".")
    new_name = uuid.uuid4()
    if len(filename_split) > 1:
        extension = filename_split[-1]
        return f"{new_name}.{extension}"
    return f"{new_name}"


class Media(models.Model):
    """Media file metadata"""

    orig_name = models.TextField()
    type = models.ForeignKey(MediaType, on_delete=models.CASCADE)
    upload_date = models.DateTimeField(default=now, editable=False)
    edit_date = models.DateTimeField(auto_now=True)
    src_url = models.URLField(max_length=255)

    class Meta:
        verbose_name_plural = "media"

    def __str__(self) -> str:
        return f"<Media - orig_file: {self.orig_name}, source: {self.src_url[:30]}...>"


class Image(models.Model):
    """Media linked to static image files"""

    meta = models.OneToOneField(Media, on_delete=models.CASCADE, primary_key=True)
    file = models.ImageField(upload_to=unique_filename, unique=True)

    """MD5 hash"""
    md5 = models.CharField(validators=[valid_md5])

    """Perceptual (DCT) hash"""
    phash = models.CharField(validators=[valid_phash])

    """Difference hash"""
    dhash = models.CharField(validators=[valid_dhash])

    # TODO: add duplicate detection
    # See https://github.com/JohannesBuchner/imagehash/issues/127 for

    def __str__(self) -> str:
        return f"<Image - meta: {self.meta}, file: {self.file}>"

    def save(self, *args, **kwargs):
        self.md5 = md5(self.file.open().read()).hexdigest()  # noqa: S324
        self.phash = str(imagehash.phash(PIL_Image.open(self.file)))
        self.dhash = str(imagehash.dhash(PIL_Image.open(self.file)))
        super().save(*args, **kwargs)


class Video(models.Model):
    """Media linked to static video files"""

    meta = models.OneToOneField(Media, on_delete=models.CASCADE, primary_key=True)
    file = models.FileField(upload_to=unique_filename, unique=True)

    """MD5 hash"""
    md5 = models.CharField(validators=[valid_md5])

    def __str__(self) -> str:
        return f"<Video - meta: {self.meta}, file: {self.file}>"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.md5 = md5(self.file.file).hexdigest()  # noqa: S324


class Audio(models.Model):
    """Media linked to static audio files"""

    meta = models.OneToOneField(Media, on_delete=models.CASCADE, primary_key=True)
    file = models.FileField(upload_to=unique_filename, unique=True)

    """MD5 hash"""
    md5 = models.CharField(validators=[valid_md5])

    def __str__(self) -> str:
        return f"<Audio - meta: {self.meta}, file: {self.file}>"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.md5 = md5(self.file.file).hexdigest()  # noqa: S324


class Post(models.Model):
    """Posts made by users with attached media"""

    uploader = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    post_date = models.DateTimeField(default=now, editable=False)
    tags = models.ManyToManyField(Tag)
    media = models.OneToOneField(Media, on_delete=models.CASCADE, primary_key=True)

    class Meta:
        ordering = ["post_date"]

    def __str__(self) -> str:
        return f"<Post - uploader: {self.uploader.name}, posted: {self.post_date}>"


class Pool(models.Model):
    """Collections of posts saved by users"""

    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    desc = models.TextField(max_length=1024)
    posts = models.ManyToManyField(Post)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="unique_pool_name_user"
            )
        ]

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

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="unique_favorite"),
        ]

    def __str__(self) -> str:
        return f"<Favorite - post: {self.post}, user: {self.user}>"
