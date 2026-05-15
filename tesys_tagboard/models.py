"""Models for Tesys's Tagboard"""

import re
import uuid
from hashlib import md5
from io import BytesIO
from typing import TYPE_CHECKING

import imagehash
from colorfield.fields import ColorField
from django.conf import settings
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import HashIndex
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import (
    BooleanField,
    Case,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.utils import timezone
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from PIL import Image as PIL_Image

from config.settings.base import AUTH_USER_MODEL

from .enums import MediaCategory, RatingLevel, SupportedMediaType
from .upload import get_file_content_type
from .validators import (
    validate_collection_name,
    validate_dhash,
    validate_md5,
    validate_mimetype,
    validate_phash,
    validate_tag_name,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from users.models import User

from django.db.models import Lookup
from django.db.models.fields import Field


@Field.register_lookup
class Like(Lookup):
    lookup_name = "like"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return f"{lhs} LIKE {rhs}", params


class TagCategory(models.Model):
    """Categories for Tags

    Tag categories may be nested into subcategories via the `parent` attribute. Checks
    are made to prevent loops when creating new categories, but otherwise categories may
    be nested as deeply as desired, though very deep trees may negatively effect
    performance.

    Attributes
        name: CharField
        parent: ForeignKey(self)
        bg: ColorField the background color for the category
        fg: ColorField the foreground color for the category
    """

    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_(
            "A parent tag category. Used for organizing tag categories into groups"
        ),
    )
    light_bg = ColorField(
        format="hex",
        null=True,
        help_text=_("Background color for tags in this category in light mode"),
        verbose_name=_("light mode background"),
    )
    light_fg = ColorField(
        format="hex",
        null=True,
        help_text=_("Text color for tags in this category in light mode"),
        verbose_name=_("light mode text"),
    )
    dark_bg = ColorField(
        format="hex",
        null=True,
        help_text=_("Background color for tags in this category in dark mode"),
        verbose_name=_("dark mode text"),
    )
    dark_fg = ColorField(
        format="hex",
        null=True,
        help_text=_("Text color for tags in this category in dark mode"),
        verbose_name=_("dark mode text"),
    )

    class Meta:
        verbose_name = _("tag category")
        verbose_name_plural = _("tag categories")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "parent"],
                name="unique_name_parent",
                nulls_distinct=False,
            ),
        ]
        indexes = [
            models.Index(fields=["name"], name="tag_category_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name}  ({self.get_full_path()})"

    def __repr__(self) -> str:
        return (
            f"<TagCategory - {self.name}, bg: {self.light_bg}, fg: {self.light_fg},"
            f"parent: {self.parent}>"
        )

    def get_full_path(self, max_depth: int = 5) -> str:
        """Return the category chain up to the root or up to `max_depth` categories"""
        category = self
        path = self.name
        for _i in range(max_depth):
            if category.parent is None:
                break

            path = f"{category.parent.name}{settings.TAG_CATEGORY_DELIMITER}{path}"
            category = category.parent

        return path


class TagManager(models.Manager):
    def get_queryset(self):
        return TagQuerySet(self.model, using=self._db)

    def for_post(self, post: Post):
        """Return tags and related category data for a specific `post`"""
        return self.get_queryset().for_post(post)

    def in_tagset(self, tagset: list[int] | None):
        """Return tags matching one of the IDs in `tagset`"""
        return self.get_queryset().in_tagset(tagset)

    def for_user(self, user: User):
        """Retrive Tags excluding any filtered tags from the User's settings"""
        return self.get_queryset().for_user(user)


class TagQuerySet(models.QuerySet):
    def for_post(self, post: Post):
        return self.select_related("category").filter(post=post)

    def in_tagset(self, tagset: list[int] | None):
        return self.select_related("category").filter(pk__in=tagset)

    def as_list(self) -> list[int]:
        """Return a list of IDs of a TagQuerySet"""
        return [t.pk for t in self]

    def for_user(self, user: User):
        filter_tag_ids = user.filter_tags.values_list("pk", flat=True)
        return self.exclude(pk__in=filter_tag_ids)


class Artist(models.Model):
    """Model for Artists to identify all artwork from a particular source"""

    tag = models.OneToOneField("Tag", on_delete=models.CASCADE, primary_key=True)
    bio = models.TextField(blank=True, default="")
    user = models.ForeignKey(AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = _("artist")
        verbose_name_plural = _("artists")

    def __str__(self) -> str:
        return f"<Artist - {self.tag}, bio: {self.bio}>"


def media_upload_path(instance, original_filename: str) -> str:
    """Generate a unique upload path for a Media file"""
    random_filename = str(uuid.uuid4())
    now = timezone.now()
    mimetype = get_file_content_type(instance.file)
    if smt := SupportedMediaType.select_by_mime(mimetype):
        return f"uploads/{now.year}/{now.month}/{now.day}/{random_filename}.{smt.value.extensions[0]}"  # noqa: E501
    msg = (
        f"A file with an unsupported media type ({instance.mimetype}) "
        "could not be uploaded"
    )
    raise ValueError(msg)


def media_thumbnail_upload_path(instance, filename: str) -> str:
    """Generate a unique upload path for a Media file thumbnail"""
    filename = str(uuid.uuid4())
    now = timezone.now()
    return f"thumbnails/{now.year}/{now.month}/{now.day}/{filename}.png"


def unique_filename(instance, filename: str) -> str:
    """Generate a unique (UUID) filename"""
    filename_split = filename.split(".")
    new_name = uuid.uuid4()
    if len(filename_split) > 1:
        extension = filename_split[-1]
        return f"{new_name}.{extension}"
    return f"{new_name}"


def update_tag_post_counts():
    tcounts = (
        Tag.post_set.through.objects.values("tag")
        .annotate(
            post_count=models.Count("post"),
            name=models.F("tag__name"),
            category=models.F("tag__category"),
            pk=models.F("tag"),
        )
        .order_by("tag__category")
    )

    tcount_tags = [Tag(pk=tc["pk"], post_count=tc["post_count"]) for tc in tcounts]
    Tag.tags.bulk_update(tcount_tags, fields=["post_count"])


def tags_to_csv(tags: Iterable[Tag]) -> str:
    return ",".join([str(tag.pk) for tag in tags])


def csv_to_tag_ids(tags_csv: str) -> Sequence[int]:
    tags_csv = tags_csv.strip()
    try:
        tag_ids = list(
            map(int, re.split(r"\s*,\s*", tags_csv) if tags_csv != "" else [])
        )
    except ValueError as e:
        msg = f'The csv string "{tags_csv}" does not contain entirely valid Tag IDs'
        raise ValueError(msg) from e
    else:
        return tag_ids


class PostManager(models.Manager):
    def get_queryset(self):
        return PostQuerySet(self.model, using=self._db)

    def all(self):
        return self.get_queryset()

    def annotate_child_posts(self):
        """Adds `child_post_ids` annotation to a QuerySet of Posts which contains a
        list of post ID's that are linked as children posts.
        """
        return self.get_queryset().annotate_child_posts()

    def annotate_fav_count(self):
        return self.get_queryset().annotate_fav_count()

    def annotate_comment_count(self):
        return self.get_queryset().annotate_comment_count()

    def annotate_favorites(self, favorites: QuerySet[Favorite]):
        """Adds the `favorited` annotation to a QuerySet of Posts"""
        return self.get_queryset().annotate_favorites(favorites)

    def has_tags(self, tags: QuerySet[Tag]):
        """Return Posts tagged with _all_ of the provided `tags`"""
        return self.get_queryset().has_tags(tags)

    def annotate_tag_count(self):
        return self.get_queryset().annotate_tag_count()

    def uploaded_by(self, user):
        """Return Posts uploaded by `user`"""
        return self.get_queryset().uploaded_by(user)

    def with_media_id(self, media_id: int):
        """Return Posts matching the given `media_id`"""
        return self.get_queryset().with_media_id(media_id)

    def with_gallery_data(self, user):
        """Return PostQuerySet including prefetched data such as media and tags"""
        return self.get_queryset().with_gallery_data(user)


class PostQuerySet(models.QuerySet):
    def annotate_favorites(self, favorites: QuerySet[Favorite]):
        return self.annotate(
            favorited=Case(
                When(
                    pk__in=favorites.values_list("post", flat=True),
                    then=Value(value=True),
                ),
                default=Value(value=False),
            )
        )

    def annotate_child_posts(self):
        child_posts_subquery = (
            Post.posts.filter(parent=OuterRef("pk"))
            .only("pk")
            .annotate(child_id_array=ArrayAgg("pk"))
        ).values("child_id_array")[:1]
        return self.annotate(
            child_post_ids=Subquery(
                child_posts_subquery,
                output_field=ArrayField(models.PositiveBigIntegerField()),
            ),
        )

    def uploaded_by(self, user):
        return self.filter(user=user)

    def with_media_id(self, media_id: int):
        return self.filter(media__id=media_id)

    def with_gallery_data(self, user: User):
        prefetch_tags = Tag.tags.select_related("category").only(
            "name", "id", "category", "post_count"
        )
        posts = (
            self.defer(
                "title",
                "post_date",
                "edit_date",
                "src_url",
                "locked_comments",
                "parent_id",
            )
            .prefetch_related(
                Prefetch("tags", queryset=prefetch_tags),
                "collection_set",
            )
            .select_related("image")
            .defer(
                "image__orig_name",
                "image__md5",
                "image__phash",
                "image__dhash",
            )
        )
        if user.is_authenticated:
            post_blur_tag_overlap = (
                Tag.tags.select_related("category")
                .filter(post=OuterRef("pk"))
                .only("pk")
                .intersection(user.blur_tags.only("pk").all())
            )
            posts = posts.annotate(
                blur_level=Q(rating_level__gte=user.blur_rating_level),
                blur_tag=Subquery(
                    post_blur_tag_overlap.values("pk"), output_field=BooleanField()
                ),
            )
            favorites = Favorite.favorites.for_user(user)
            posts = posts.exclude(tags__in=user.filter_tags.all()).annotate_favorites(
                favorites
            )
        else:
            posts.annotate(
                blur_level=Q(rating_level__gte=RatingLevel.EXPLICIT),
            )
        return posts

    def has_tags(self, tags: QuerySet[Tag]):
        filter_expr = self
        for tag in tags:
            filter_expr = filter_expr & self.filter(tags__in=[tag.pk])

        return filter_expr

    def annotate_comment_count(self):
        return self.annotate(comment_count=models.Count("comment"))

    def annotate_fav_count(self):
        return self.annotate(fav_count=models.Count("favorite"))

    def annotate_tag_count(self):
        return self.annotate(tag_count=models.Count("tags"))


class Post(models.Model):
    """Posts made by users with attached media"""

    title = models.TextField(default="", max_length=1000)
    uploader = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    post_date = models.DateTimeField(default=now, editable=False)
    edit_date = models.DateTimeField(auto_now=True)
    tags = models.ManyToManyField("Tag", blank=True)
    rating_level = models.PositiveSmallIntegerField(
        default=RatingLevel.UNRATED,
        choices=RatingLevel.choices,
    )
    src_url = models.URLField(max_length=255, blank=True, default="")
    locked_comments = models.BooleanField(default=False, blank=True)

    media_choices = (
        (x.name, x.value.desc) for x in SupportedMediaType.__members__.values()
    )
    type = models.CharField(max_length=20, choices=media_choices)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True)

    posts = PostManager()

    class Meta:
        verbose_name = _("post")
        verbose_name_plural = _("posts")
        permissions = [("lock_comments", "Can lock and unlock the comments of a post")]
        ordering = ["post_date"]

    def __str__(self) -> str:
        return f"<Post - id: {self.pk}; uploader: {self.uploader.username}; title: {self.title}; posted: {self.post_date}>"  # noqa: E501

    # TODO: also override update() to update post counts
    def save_and_update_post_count(self, **kwargs):
        super().save(**kwargs)
        update_tag_post_counts()

    def save_with_tag_history(self, user, tags: TagQuerySet):
        """Saves the post with additional handling for tag history"""
        add_tag_history(tags, self, user)
        self.tags.set(tags)
        self.save()

    def save_with_src_history(self, user, src_url: str):
        """Saves the Media with additional handling for source history"""
        source_hist = SourceHistory.objects.filter(post=self)
        if (self.src_url != src_url or not source_hist) and not src_url.isspace():
            SourceHistory(post=self, user=user, src_url=src_url).save()
            self.src_url = src_url
        self.save()

    def tagset(self) -> set[int]:
        """Returns set of tag IDs"""
        return set(self.tags.all().values_list("pk", flat=True))

    def category(self) -> MediaCategory | None:
        if hasattr(self, "audio"):
            return MediaCategory.AUDIO
        if hasattr(self, "image"):
            return MediaCategory.IMAGE
        if hasattr(self, "video"):
            return MediaCategory.VIDEO
        return None

    def file(self):
        match self.category():
            case MediaCategory.AUDIO:
                return self.audio
            case MediaCategory.IMAGE:
                return self.image
            case MediaCategory.VIDEO:
                return self.video
        return None


class Tag(models.Model):
    """Tags for Posts. They are used for "tagging" Posts and searching

    Attributes
        name: CharField
        category: CharField(2)
        description: TextField(255)
        post_count: PositiveIntegerField
        rating_level: PositiveSmallIntegerField
    """

    name = models.CharField(max_length=100, validators=[validate_tag_name])
    category = models.ForeignKey(
        TagCategory, null=True, on_delete=models.CASCADE, blank=True
    )
    description = models.TextField(max_length=255, blank=True, default="")
    post_count = models.PositiveIntegerField(default=0)

    """Rating levels to filter content. This field allows any tag to apply a rating
    """
    rating_level = models.PositiveSmallIntegerField(
        default=0, choices=RatingLevel.choices, blank=True
    )

    tags = TagManager()

    class Meta:
        verbose_name = _("tag")
        verbose_name_plural = _("tags")
        ordering = ["category", "-post_count"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "category"],
                name="unique_tag_name_cat",
                nulls_distinct=False,
            ),
        ]

    def __str__(self) -> str:
        if category := self.category.get_full_path() if self.category else "":
            return f"{self.name} ({category})"
        return self.name

    def __repr__(self) -> str:
        return f"<Tag - {self.name}, category: {self.category}>"

    def get_full_path(self, max_depth: int = 5) -> str:
        """Return the tag and category chain up to the root or up to a `max_depth`
        of categories"""
        if self.category:
            return (
                self.category.get_full_path(max_depth=max_depth)
                + settings.TAG_CATEGORY_DELIMITER
                + self.name
            )

        return self.name


class TagAliasManager(models.Manager):
    def get_queryset(self):
        return TagAliasQuerySet(self.model, using=self._db)

    def for_user(self, user: User):
        """Retrive TagAliases excluding any filtered tags from the User's settings"""
        return self.get_queryset().for_user(user)


class TagAliasQuerySet(models.QuerySet):
    def for_user(self, user: User):
        """Retrive TagAliases excluding any filtered tags from the User's settings"""
        return self.exclude(tag__in=user.filter_tags.all())


class TagAlias(models.Model):
    """Aliases for Tags"""

    name = models.CharField(max_length=100, validators=[validate_tag_name])
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    aliases = TagAliasManager()

    class Meta:
        verbose_name = _("tag alias")
        verbose_name_plural = _("tag aliases")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "tag"], name="unique_tagalias_name_tag"
            ),
        ]

    def __str__(self) -> str:
        return f"<TagAlias - {self.name}, tag: {self.tag}>"


class DefaultPostTag(models.Model):
    """Default Tags applied to new Posts"""

    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, primary_key=True)

    class Meta:
        verbose_name = _("default post tag")
        verbose_name_plural = _("default post tags")

    def __str__(self) -> str:
        return f"<DefaultPostTag - {self.tag}>"


def add_tag_history(tags: QuerySet[Tag], post: Post, user):
    old_tags = set(post.tags.order_by("pk"))
    new_tags = set(tags.all())
    tag_histories = PostTagHistory.objects.filter(post=post)
    if old_tags != new_tags or not tag_histories:
        tag_hist = PostTagHistory(post=post, user=user, tags=tags_to_csv(tags.all()))
        tag_hist.save()


class Image(models.Model):
    """Media linked to static image files"""

    post = models.OneToOneField(Post, on_delete=models.CASCADE, null=True)
    mimetype = models.CharField(max_length=30, validators=[validate_mimetype])
    orig_name = models.TextField(default="")
    file = models.ImageField(
        upload_to=media_upload_path,
        unique=True,
        width_field="width",
        height_field="height",
    )
    width: models.PositiveIntegerField = models.PositiveIntegerField(default=0)
    height: models.PositiveIntegerField = models.PositiveIntegerField(default=0)
    thumbnail = models.ImageField(
        upload_to=media_thumbnail_upload_path,
        width_field="thumbnail_width",
        height_field="thumbnail_height",
        null=True,
    )
    thumbnail_width: models.PositiveIntegerField = models.PositiveIntegerField(
        default=0
    )
    thumbnail_height: models.PositiveIntegerField = models.PositiveIntegerField(
        default=0
    )

    """MD5 hash"""
    md5 = models.CharField(validators=[validate_md5])

    """Perceptual (DCT) hash"""
    phash: models.CharField = models.CharField(validators=[validate_phash])

    """Difference hash"""
    dhash: models.CharField = models.CharField(validators=[validate_dhash])

    # TODO: add duplicate detection
    # See https://github.com/JohannesBuchner/imagehash/issues/127 for

    class Meta:
        verbose_name = _("image")
        verbose_name_plural = _("images")
        indexes = [
            HashIndex("md5", name="image_md5_idx"),
            HashIndex("phash", name="image_phash_idx"),
            HashIndex("dhash", name="image_dhash_idx"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.md5 = md5(self.file.open().read()).hexdigest()  # noqa: S324
        image_file = PIL_Image.open(self.file)
        self.phash = str(imagehash.phash(image_file))
        self.dhash = str(imagehash.dhash(image_file))

    def __str__(self) -> str:
        return (
            f"<Image - file: {self.file}, width: {self.width}, height: {self.height}>"
        )

    def save(self, *args, **kwargs):
        image_file = PIL_Image.open(self.file)

        # Set thumbnail size
        thumb_size = kwargs.get("thumb_size", (400, 400))
        image_file.thumbnail(thumb_size)

        # Save thumbnail to memory
        handle = BytesIO()
        image_file.save(handle, "png")
        handle.seek(0)

        thumbnail_name = f"{self.file.name}.png"
        suf = SimpleUploadedFile(
            thumbnail_name, handle.read(), content_type="image/png"
        )

        self.thumbnail.save(f"{suf.name}.png", suf, save=False)
        self.thumbnail_width, self.thumbnail_height = image_file.size

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)

    def category(self):
        return MediaCategory.IMAGE


class Video(models.Model):
    """Media linked to static video files"""

    post = models.OneToOneField(Post, on_delete=models.CASCADE, null=True)
    mimetype = models.CharField(max_length=30, validators=[validate_mimetype])
    orig_name = models.TextField(default="")
    file = models.FileField(upload_to=media_upload_path, unique=True)

    """MD5 hash"""
    md5 = models.CharField(validators=[validate_md5])

    class Meta:
        verbose_name = _("video")
        verbose_name_plural = _("videos")
        indexes = [
            HashIndex("md5", name="video_md5_idx"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.md5 = md5(self.file.open().read()).hexdigest()  # noqa: S324

    def __str__(self) -> str:
        return f"<Video - file: {self.file}>"

    def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)

    def category(self):
        return MediaCategory.VIDEO


class Audio(models.Model):
    """Media linked to static audio files"""

    post = models.OneToOneField(Post, on_delete=models.CASCADE, null=True)
    mimetype = models.CharField(max_length=30, validators=[validate_mimetype])
    orig_name = models.TextField(default="")
    file = models.FileField(upload_to=media_upload_path, unique=True)

    """MD5 hash"""
    md5 = models.CharField(validators=[validate_md5])

    class Meta:
        verbose_name = _("audio")
        verbose_name_plural = _("audios")
        indexes = [
            HashIndex("md5", name="audio_md5_idx"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.md5 = md5(self.file.open().read()).hexdigest()  # noqa: S324

    def __str__(self) -> str:
        return f"<Audio - file: {self.file}>"

    def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)

    def category(self):
        return MediaCategory.AUDIO


class SourceHistory(models.Model):
    """Model for tracking changes in a Post's src_url"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    mod_time = models.DateTimeField(
        auto_now_add=True,
        db_comment="Timestamp of Media's source URL modification (including initial)",
    )
    src_url = models.CharField(
        db_comment="Comma-delimited string of source URLs at the current time",
        default="",
    )

    class Meta:
        verbose_name = _("source history")
        verbose_name_plural = _("source histories")

    def __str__(self) -> str:
        return f"<MediaSourceHistory - post: {self.post}, mod_time: {self.mod_time}, source: {self.src_url}>"  # noqa: E501


class PostTagHistory(models.Model):
    """Model for tracking changes in a Post's tags"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    mod_time = models.DateTimeField(
        auto_now_add=True,
        db_comment="Timestamp of Post's tags modification (including initial)",
    )
    tags = models.CharField(
        db_comment="Comma-delimited string of tag IDs at the current time",
        default="",
    )

    class Meta:
        verbose_name = _("post tag history")
        verbose_name_plural = _("post tag histories")

    def __str__(self) -> str:
        return f"<PostTagHistory - id: {self.pk}; post: {self.post}; modified: {self.mod_time};"  # noqa: E501


class CollectionQuerySet(models.QuerySet):
    def public(self):
        """Returns only `public` Collections"""
        return self.filter(public=True)

    def for_user(self, user_id):
        """Return Collections of a `user`"""
        return self.filter(user=user_id).select_related("user")

    def with_gallery_data(self):
        """Return optimized CollectionQuerySet including gallery data
        such as related posts for the given user"""
        return self.prefetch_related("posts").select_related("user")


class Collection(models.Model):
    """Collections of posts saved by users"""

    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(
        max_length=128, validators=[validate_collection_name, MaxLengthValidator(128)]
    )
    desc = models.TextField(max_length=1024, validators=[MaxLengthValidator(500)])
    posts = models.ManyToManyField(Post)
    public = models.BooleanField(default=True, blank=True)

    objects = CollectionQuerySet.as_manager()

    class Meta:
        verbose_name = _("collection")
        verbose_name_plural = _("collections")
        permissions = [
            ("add_post_to_collection", "Can add posts to a collection"),
            ("remove_post_from_collection", "Can remove posts from a collection"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="unique_collection_name_user"
            )
        ]

    def __str__(self) -> str:
        return f"<Collection - name: {self.name}, user: {self.user}, desc: {self.desc}>"


class CommentQuerySet(models.QuerySet):
    def for_post(self, post_id: int):
        """Returns comments for the specified `post_id`"""
        return self.filter(post__pk=post_id).order_by("-post_date")


class Comment(models.Model):
    """User comments"""

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        db_comment="The foreign key to the Post this comment comments on",
    )
    user = models.ForeignKey(
        AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        db_comment="The foreign key to the User who posted the comment",
    )
    text = models.TextField(
        editable=True, max_length=500, db_comment="The body text of the comment"
    )
    post_date = models.DateTimeField(
        auto_now_add=True, db_comment="Date and time when the comment was posted"
    )
    edit_date = models.DateTimeField(
        auto_now=True, db_comment="Date and time when the comment was last edited"
    )

    objects = CommentQuerySet.as_manager()

    class Meta:
        verbose_name = _("comment")
        verbose_name_plural = _("comments")
        ordering = ["-post_date"]

    def __str__(self) -> str:
        return f'<Comment: user: {self.user}, text: "{self.text}">'


class FavoriteManager(models.Manager):
    def get_queryset(self):
        return FavoriteQuerySet(self.model, using=self._db)

    def for_user(self, user_id):
        return self.get_queryset().for_user(user_id)

    def with_gallery_data(self):
        return self.get_queryset().with_gallery_data()


class FavoriteQuerySet(models.QuerySet):
    def for_user(self, user_id):
        return self.filter(user=user_id)

    def with_gallery_data(self):
        return self.select_related("post", "post", "post__image").prefetch_related(
            "post__tags"
        )


class Favorite(models.Model):
    """Favorited posts by users"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    favorites = FavoriteManager()

    class Meta:
        verbose_name = _("favorite")
        verbose_name_plural = _("favorites")
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="unique_favorite"),
        ]

    def __str__(self) -> str:
        return f"<Favorite - post: {self.post}, user: {self.user.username}>"
