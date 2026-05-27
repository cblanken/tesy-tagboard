from dataclasses import dataclass
from enum import StrEnum
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, LiteralString

import psycopg
import typer
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.files import File
from django.core.files.images import ImageFile
from django.db import IntegrityError
from django.db.models import Model, Q
from django_typer.management import Typer
from faker import Faker
from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, track
from rich.style import Style
from rich.theme import Theme

from tesys_tagboard.enums import MediaCategory, RatingLevel, SupportedMediaType
from tesys_tagboard.models import (
    Audio,
    Collection,
    Comment,
    Image,
    Post,
    PostTagHistory,
    SourceHistory,
    Tag,
    TagAlias,
    TagCategory,
    Video,
    tags_to_csv,
)
from tesys_tagboard.users.models import User


class STYLE(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"


custom_theme = Theme(
    {
        STYLE.INFO: Style(color="white", blink=False, bold=False),
        STYLE.SUCCESS: Style(color="green", blink=False, bold=False),
        STYLE.WARNING: Style(color="yellow", blink=False, bold=True),
        STYLE.DANGER: Style(color="red", blink=False, bold=True),
    }
)


console = Console(theme=custom_theme)

Faker.seed(0)
fake = Faker()

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Iterable


DEFAULT_USER_GROUP = Group.objects.get(name="Users")
DEFAULT_MOD_GROUP = Group.objects.get(name="Moderators")

app = Typer()


def fetch_shimmie_data(
    db: Connection, query: LiteralString, desc: str
) -> list[DictRow]:
    """Fetches data from the Shimmie2 database using the provided query
    and returning results as DictRow(s) while showing a progress bar."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Retrieving images from Shimmie2...", total=None)
        data: list[DictRow] = db.cursor(row_factory=dict_row).execute(query).fetchall()

    return data


def delete_recursively(path: Path):
    for root, dirs, files in path.walk(top_down=False):
        for file in files:
            Path(root / file).unlink()
        for d in dirs:
            Path(root / d).rmdir()


@app.command()
def main(  # noqa: PLR0913
    conn_str: Annotated[
        str, typer.Argument(help="Connection string to the target Shimmie2 database.")
    ],
    data_dir: Annotated[
        Path, typer.Argument(help="Path to the Shimmie2 data directory.")
    ],
    *,
    feat_all: Annotated[
        bool,
        typer.Option("--all", "-a", help="Include data from all supported features."),
    ] = False,
    feat_users: Annotated[
        bool,
        typer.Option("--users", "-u", help="Include data of all users."),
    ] = False,
    feat_tags: Annotated[
        bool,
        typer.Option("--tags", "-t", help="Include data of all tags."),
    ] = False,
    feat_tag_histories: Annotated[
        bool,
        typer.Option("--tag-histories", help="Include tag history data."),
    ] = False,
    feat_tag_categories: Annotated[
        bool,
        typer.Option("--tag-categories", help="Include data of all tag categories."),
    ] = False,
    feat_posts: Annotated[
        bool,
        typer.Option(
            "--tag-images",
            "-i",
            help="Include data of all posts and their related media and metadata",
        ),
    ] = False,
    feat_collections: Annotated[
        bool,
        typer.Option(
            "--collections",
            "-c",
            help="Include data of all collections/pools",
        ),
    ] = False,
    feat_comments: Annotated[
        bool,
        typer.Option(
            "--comments",
            help="Include data of all post comments",
        ),
    ] = False,
    feat_post_source_histories: Annotated[
        bool,
        typer.Option(
            "--post-source-histories",
            help="Include historical data of post source changes",
        ),
    ] = False,
):
    """
    A command to migrate data from a live Shimmie2 (https://github.com/shish/shimmie2)
    instance into the local Tesy's Tagboard application.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Deleting old DB data...", total=None)
        TagCategory.objects.filter(~Q(name="artist") & ~Q(name="copyright")).delete()
        Tag.tags.all().delete()
        TagAlias.aliases.all().delete()
        Post.posts.all().delete()
        User.objects.exclude(is_staff=True).delete()
        Collection.objects.all().delete()

        progress.add_task(description="Deleting old media files...", total=None)
        media_root = Path(settings.MEDIA_ROOT)
        thumbnails_dir = media_root / "thumbnails"
        delete_recursively(thumbnails_dir)
        uploads_dir = media_root / "uploads"
        delete_recursively(uploads_dir)

    console.print("Old data deleted.", style=STYLE.INFO)

    db = psycopg.connect(conn_str)
    db.read_only = True

    if feat_users or feat_all or feat_posts or feat_collections:
        migrate_users(db)

    if feat_tags or feat_tag_categories or feat_tag_histories or feat_all or feat_posts:
        migrate_tags(db)

    if feat_tag_categories or feat_tag_histories or feat_all:
        migrate_tag_categories(db)

    if (
        feat_posts
        or feat_all
        or feat_tag_histories
        or feat_collections
        or feat_comments
    ):
        migrate_images(db, data_dir)

    if feat_tag_histories or feat_all:
        migrate_tag_histories(db)

    if feat_post_source_histories or feat_all:
        migrate_post_source_histories(db)

    if feat_collections or feat_all:
        migrate_pools(db)

    if feat_comments or feat_all:
        migrate_comments(db)


@dataclass
class ShimmieUser:
    username: str
    password: str
    joindate: dt.datetime
    user_class: str
    email: str


def migrate_users(db: Connection):
    shimmie_users = fetch_shimmie_data(
        db,
        query="SELECT id, name, pass, joindate, class, email FROM users;",
        desc="Retrieving users from Shimmie2",
    )

    console.print(f"Retrieved {len(shimmie_users)} users from Shimmie2.")

    # TODO: accept arg to set timezones since Shimmie only provided naive datetimes
    new_users = [
        User(
            id=user.get("id"),
            username=user.get("name"),
            password=f"bcrypt${user.get('pass')}" or "",
            date_joined=user.get("joindate").astimezone(),
        )
        for user in shimmie_users
    ]

    for user in track(new_users, description="Creating users"):
        user.save()
        user.add_to_group(DEFAULT_USER_GROUP.name)
        # TODO: handle errors for invalid usernames, and other errors
        # TODO: handle user class distinctions such as Mod or Admin roles


def migrate_tags(db: Connection):
    shimmie_tags = fetch_shimmie_data(
        db,
        query="SELECT id, tag, count FROM tags;",
        desc="Retrieving tags from Shimmie2",
    )

    console.print(f"Retrieved {len(shimmie_tags)} tags from Shimmie2.")

    # TODO: accept arg to set timezones since Shimmie only provided naive datetimes
    tags = [
        Tag(id=tag.get("id"), name=tag.get("tag"), post_count=tag.get("count"))
        for tag in shimmie_tags
    ]

    save_models(tags, Tag)

    shimmie_tag_aliases = fetch_shimmie_data(
        db,
        query="SELECT oldtag, newtag FROM aliases;",
        desc="Retrieving tag aliases from Shimmie2",
    )
    console.print(f"Retrieved {len(shimmie_tag_aliases)} tag aliases from Shimmie2.")

    tag_aliases = [
        TagAlias(
            name=tag_alias.get("oldtag"), tag=Tag.tags.get(name=tag_alias.get("newtag"))
        )
        for tag_alias in shimmie_tag_aliases
        if len(tag_alias.get("newtag", "").strip()) != 0
    ]
    save_models(tag_aliases, TagAlias)


def migrate_tag_categories(db: Connection):
    shimmie_tag_categories = fetch_shimmie_data(
        db,
        query="SELECT category, color FROM image_tag_categories;",
        desc="Retrieving tag categories from Shimmie2",
    )

    console.print(
        f"Retrieved {len(shimmie_tag_categories)} tag categories from Shimmie2."
    )

    # TODO: accept arg to set timezones since Shimmie only provided naive datetimes
    tag_categories = [
        TagCategory(
            name=tag_category.get("category"), light_fg=tag_category.get("color")
        )
        for tag_category in shimmie_tag_categories
    ]

    save_models(tag_categories, TagCategory)


def migrate_pools(db: Connection):
    shimmie_pools = fetch_shimmie_data(
        db,
        query="SELECT id, user_id, public, title, description FROM pools;",
        desc="Retrieving pool/collection metadata from Shimmie2",
    )

    # TODO: accept arg to set timezones since Shimmie only provided naive datetimes
    collections = [
        Collection.objects.create(
            id=pool.get("id"),
            name=pool.get("title", ""),
            desc=pool.get("description", ""),
            public=pool.get("public", False),
            user_id=pool.get("user_id"),
        )
        for pool in shimmie_pools
    ]

    save_models(collections, Collection)

    shimmie_pool_images = fetch_shimmie_data(
        db,
        query="SELECT pool_id, image_id FROM pool_images",
        desc="Retrieving pool/collection image references from Shimmie2",
    )

    linked_collections = 0
    for collection in track(
        collections, description="Linking collections with their posts"
    ):
        pool_images = filter(
            lambda pool_image: int(pool_image.get("pool_id") == collection.pk),
            shimmie_pool_images,
        )

        post_ids = [int(pool_image.get("pool_id")) for pool_image in pool_images]
        collection_posts = Post.posts.filter(pk__in=post_ids)
        collection.posts.set(collection_posts)
        linked_collections += 1

    console.print(
        f"Linked {linked_collections} collections with their posts from Shimmie2."
    )


def link_tags_to_posts(db):
    shimmie_image_tags = fetch_shimmie_data(
        db,
        query="SELECT image_id, tag_id FROM image_tags;",
        desc="Retrieving image tags from Shimmie2",
    )

    linked_tags_count = 0

    posts = Post.posts.all()
    for post in posts:
        post_image_tags = filter(
            lambda image_tag: int(image_tag.get("image_id") == post.pk),
            shimmie_image_tags,
        )
        tag_ids = [int(image_tag.get("tag_id")) for image_tag in post_image_tags]
        post_tags = Tag.tags.in_tagset(tag_ids)
        post.tags.set(post_tags)
        post.save()
        linked_tags_count += 1
    console.print(f"Linked {linked_tags_count} posts with their tags")


def link_post_parents(db):
    shimmie_images_with_parents = fetch_shimmie_data(
        db,
        query="""
            SELECT images.id as id, parent_id
            FROM images
            WHERE parent_id IS NOT NULL;
        """,
        desc="Retrieving images from Shimmie2",
    )

    linked_parent_count = 0
    for image in track(
        shimmie_images_with_parents, description="Linking post parents and children"
    ):
        post_id = image.get("id")
        parent_id = image.get("parent_id")
        Post.posts.filter(id=post_id).update(parent_id=parent_id)
        linked_parent_count += 1
    console.print(f"Linked {linked_parent_count} posts with their parents")


def migrate_images(db: Connection, data_dir: Path):
    """Note that in Shimmie2 the `image` table refers to the equivalent of
    Posts in Tesy's Tagboard. However the relevant media metadata for Images,
    Audios, and Video reside in seperate models in Tesy's Tagboard"""
    shimmie_rating_map = {
        "?": RatingLevel.UNRATED,
        "s": RatingLevel.SAFE,
        "q": RatingLevel.QUESTIONABLE,
        "e": RatingLevel.EXPLICIT,
    }

    users = User.objects.all()
    shimmie_images = fetch_shimmie_data(
        db,
        query="""
            SELECT
                images.id as id,
                title,
                users.name as username,
                users.email as email,
                posted,
                rating,
                comments_locked,
                ext,
                parent_id,
                hash,
                width,
                height
            FROM images JOIN users ON images.owner_id = users.id;
        """,
        desc="Retrieving images from Shimmie2",
    )

    console.print(f"Retrieved {len(shimmie_images)} images from Shimmie2.")

    # TODO: accept arg to set timezones since Shimmie only provided naive datetimes
    posts: list[Post] = []
    audios: list[Audio] = []
    images: list[Image] = []
    videos: list[Video] = []
    # Create initial Posts from Shimmie images
    for image in track(shimmie_images, description="Creating Post objects"):
        uploader_q = Q(username=image.get("username"))
        if uploader_email := image.get("email"):
            uploader_q &= Q(email=uploader_email)
        uploader = users.get(uploader_q)
        media_type = SupportedMediaType.select_by_ext(image.get("ext", ""))
        post_id = image.get("id")

        post = Post(
            id=post_id,
            title=image.get("title", "") or "",
            uploader=uploader,
            post_date=image.get("posted").astimezone(),
            rating_level=shimmie_rating_map.get(
                str(image.get("rating")), RatingLevel.UNRATED
            ),
            src_url=image.get("source", ""),
            locked_comments=image.get("comments_locked", False),
            type=media_type.name if media_type else None,
        )
        posts.append(post)

        post_hash = image.get("hash", "")
        post_filename = image.get("filename", "")
        post_width = image.get("width")
        post_height = image.get("height")
        media_file_path = Path(data_dir / "images" / post_hash[:2] / post_hash)
        if media_type:
            match media_type.value.category:
                case MediaCategory.AUDIO:
                    audios.append(
                        Audio(
                            file=File(media_file_path.open("rb")),
                            post=post,
                            md5=post_hash,
                            mimetype=media_type.value.get_mimetype(),
                            orig_name=post_filename,
                        )
                    )
                case MediaCategory.IMAGE:
                    images.append(
                        Image(
                            file=ImageFile(media_file_path.open("rb")),
                            post=post,
                            md5=post_hash,
                            mimetype=media_type.value.get_mimetype(),
                            orig_name=post_filename,
                            width=post_width,
                            height=post_height,
                        )
                    )
                case MediaCategory.VIDEO:
                    videos.append(
                        Video(
                            file=File(media_file_path.open("rb")),
                            post=post,
                            md5=post_hash,
                            mimetype=media_type.value.get_mimetype(),
                            orig_name=post_filename,
                            # TODO: add Video height and width
                            # TODO: add Video length
                        )
                    )
        else:
            console.print(
                f"The media type for post (id = {post_id}) either isn't supported, "
                "or it could not be correctly identified."
            )

    save_models(posts, Post)
    save_models(audios, Audio)
    save_models(images, Image)
    save_models(videos, Video)

    link_post_parents(db)
    link_tags_to_posts(db)


def migrate_tag_histories(db: Connection):
    shimmie_tag_histories = fetch_shimmie_data(
        db,
        query="SELECT image_id, user_id, tags, date_set count FROM tag_histories;",
        desc="Retrieving tag histories from Shimmie2",
    )

    console.print(f"Retrieved {len(shimmie_tag_histories)} tags from Shimmie2.")

    tag_histories: list[PostTagHistory] = []
    for tag_history in shimmie_tag_histories:
        post = Post.posts.get(pk=tag_history.get("image_id"))
        user_id = tag_history.get("user_id")
        mod_time = tag_history.get("date_set")
        tag_names = tag_history.get("tags", "").split()
        # TODO: handle option tag category parsing with provided delimiter argument
        tags = Tag.tags.filter(Q(name__in=tag_names) | Q(tagalias__name__in=tag_names))

        if len(tag_names) != tags.count():
            console.log(
                f"The tag history entry {tag_history} has some tags, that could not be "
                "found in the Tesy's Tagboard database. They may have been missed "
                " or skipped during tag migration or be missing an alias. ",
                style=STYLE.WARNING,
            )
            console.log(
                f"Shimmie tags: {tag_names}\n"
                f"Tesy's Tagboard tags: {[tag.name for tag in tags]}",
            )

        # TODO: accept arg to set timezones since Shimmie only provided naive datetimes
        tag_histories.append(
            PostTagHistory.objects.create(
                post=post, user_id=user_id, mod_time=mod_time, tags=tags_to_csv(tags)
            )
        )

    save_models(tag_histories, PostTagHistory)


def migrate_post_source_histories(db: Connection):
    shimmie_post_source_histories = fetch_shimmie_data(
        db,
        query="SELECT image_id, user_id, source, date_set FROM source_histories;",
        desc="Retrieving post source histories from Shimmie2",
    )

    console.print(f"Retrieved {len(shimmie_post_source_histories)} tags from Shimmie2.")

    post_source_histories: list[SourceHistory] = []
    for source_history in track(
        shimmie_post_source_histories, description="Creating post source histories"
    ):
        post_id = source_history.get("image_id")
        user_id = source_history.get("user_id")
        mod_time = source_history.get("date_set")
        src_url = source_history.get("source")

        post_source_histories.append(
            SourceHistory.objects.create(
                post_id=post_id, user_id=user_id, mod_time=mod_time, src_url=src_url
            )
        )

    save_models(post_source_histories, SourceHistory)


def migrate_comments(db: Connection):
    shimmie_post_comments = fetch_shimmie_data(
        db,
        query="SELECT id, image_id, owner_id, comment FROM comments;",
        desc="Retrieving post comments from Shimmie2",
    )

    console.print(
        f"Retrieved {len(shimmie_post_comments)} post comments from Shimmie2."
    )

    post_comments: list[Comment] = []
    for comment in track(shimmie_post_comments, description="Creating post comments"):
        post_id = comment.get("image_id")
        user_id = comment.get("owner_id")
        text = comment.get("comment")
        post_date = comment.get("posted")

        post_comments.append(
            Comment.objects.create(
                post_id=post_id, user_id=user_id, text=text, post_date=post_date
            )
        )

    save_models(post_comments, Comment)


def save_models(models: Iterable[Model], typ: type[Model]):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        with progress:
            saved_count = 0
            for model in track(
                models,
                description=f"Saving {typ._meta.verbose_name_plural}",  # noqa: SLF001
            ):
                try:
                    model.save()
                except IntegrityError as err:
                    progress.print(
                        f'The {typ._meta.verbose_name} "{model}" may already exist. '  # noqa: SLF001
                        f"{err}"
                    )
                else:
                    saved_count += 1

        console.print(f"Saved {saved_count} {typ._meta.verbose_name_plural}")  # noqa: SLF001
        return saved_count


def get_media_files_from_disk(
    path: Path, *, recursive: bool = True, max_files: int = 1000
) -> Iterable[Path]:
    """Imports media (audios, images, or videos) from disk"""
    media_files = []
    if recursive:
        media_files = (f for f in path.glob("**") if f.is_file())
    else:
        media_files = (f for f in path.glob("*") if f.is_file())

    return islice(media_files, max_files)
