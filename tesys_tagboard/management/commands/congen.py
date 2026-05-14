import sys
from itertools import chain, islice
from pathlib import Path
from random import choice, choices, randint, sample
from typing import TYPE_CHECKING, Annotated

import magic
import typer
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from django_typer.management import Typer
from faker import Faker
from PIL import UnidentifiedImageError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, track

from tesys_tagboard.enums import MediaCategory, RatingLevel, SupportedMediaType
from tesys_tagboard.models import (
    Audio,
    Collection,
    Comment,
    Favorite,
    Image,
    Post,
    Tag,
    TagAlias,
    TagCategory,
    Video,
    add_tag_history,
    update_tag_post_counts,
)
from tesys_tagboard.upload import fix_upload_content_type
from tesys_tagboard.users.models import User
from tesys_tagboard.validators import media_file_supported_validator

console = Console()

Faker.seed(0)
fake = Faker()

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models import QuerySet


DEFAULT_USER_USERNAMES = ["user1", "user2", "user3"]
DEFAULT_MOD_USERNAMES = ["mod1", "mod2", "mod3"]
DEFAULT_USER_GROUP = Group.objects.get(name="Users")
DEFAULT_MOD_GROUP = Group.objects.get(name="Moderators")

app = Typer()


def delete_recursively(path: Path):
    for root, dirs, files in path.walk(top_down=False):
        for file in files:
            Path(root / file).unlink()
        for d in dirs:
            Path(root / d).rmdir()


@app.command()
def main(  # noqa: PLR0913
    media_dir: Annotated[str, typer.Argument()],
    max_tags: Annotated[
        int,
        typer.Option(
            "--max-tags", "-t", help="The maximum number of tags to randomly generate."
        ),
    ] = 500,
    max_tag_categories: Annotated[
        int,
        typer.Option(
            "--max-tag-categories",
            help="The maximum number of tag categories to randomly generate",
        ),
    ] = 500,
    max_users: Annotated[
        int,
        typer.Option(
            "--max-users",
            "-u",
            help="The maximum number of users to randomly generate.",
        ),
    ] = 200,
    max_posts: Annotated[
        int,
        typer.Option(
            "--max-posts",
            "-p",
            help="The maximum number of posts to randomly generate.",
        ),
    ] = 500,
    max_collections: Annotated[
        int,
        typer.Option(
            "--max-collections",
            "-c",
            help="The maximum number of collections to randomly generate.",
        ),
    ] = 50,
    max_posts_per_collection: Annotated[
        int,
        typer.Option(
            help="The maximum number of posts to link to any single collection"
        ),
    ] = 50,
    max_favorites_per_user: Annotated[
        int,
        typer.Option(
            help="The maximum number of favorited posts to link to any single user"
        ),
    ] = 50,
):
    """
    A command to create demo data for testing the app. Media files must be loaded from
    disk. The provided `media_dir` will be searched recursively for any supported files
    and create posts from them. All other data such as Tags, Comments, Collections, and
    Users will be generated randomly with options to adjust the thresholds.
    """

    media_dir_path = Path(media_dir)
    if not media_dir_path.exists():
        console.print(
            f"Error: The target media directory ({media_dir}) could not be found. Please note that if congen.py was executed via Docker then only files within the project directory will be available to the docker container.",  # noqa: E501
            style="bold red on black",
        )

        sys.exit(1)

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

    console.print("Old data deleted.")

    # Create default users
    default_users = User.objects.bulk_create(
        [User(username=name) for name in DEFAULT_USER_USERNAMES]
    )
    default_mods = User.objects.bulk_create(
        [User(username=name) for name in DEFAULT_MOD_USERNAMES]
    )

    for user in default_users + default_mods:
        user.save()

    # Apply default groups to default users
    DEFAULT_USER_GROUP.user_set.set(default_users + default_mods)
    DEFAULT_MOD_GROUP.user_set.set(default_mods)

    create_random_users(max_users)

    create_random_tag_categories(max_tag_categories)

    create_random_tags(max_tags)

    create_random_tag_aliases(Tag.tags.all())

    media_files = get_media_files_from_disk(media_dir_path, max_files=max_posts)
    create_random_posts(media_files, user_select_max=50, max_posts=max_posts)

    create_random_post_collections(Post.posts.all(), max_collections=max_collections)

    create_random_user_favorites(
        Post.posts.all(),
        User.objects.all(),
        max_favorites_per_user=max_favorites_per_user,
    )


def create_random_users(n: int = 50):
    """Create `n` randomized Users
    Note each user's password is the same as their username repeated twice
    """
    n = min(n, 10_000)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Creating random users...", total=None)
        random_user_names = fake.words(
            n, ext_word_list=[fake.user_name() for _ in range(n * 2)], unique=True
        )
        users = [
            User(username=name, password=fake.password(20))
            for name in random_user_names
        ]
        random_users = User.objects.bulk_create(users)
        for user in random_users:
            user.save()
        DEFAULT_USER_GROUP.user_set.add(*random_users)

    console.print(f"Created {len(users)} users.")


def create_random_tag_categories(max_categories: int = 100, max_branches: int = 5):
    """Create `max_categories` randomized tag categories with a maximum depth
     and branching factor.

    Args:
        max_categories: int = the number of categories to create in total
        max_depth: int = the maximum depth of any category hierarchy
        max_branches: int = the maximum number of sub-categories a category may have
    """
    max_categories = min(max_categories, 1000)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Creating random tag categories...", total=None)

        tag_category_hierarchy = [
            [TagCategory(name=fake.word()) for _ in range(randint(1, max_branches))]
            for _ in range(settings.MAX_TAG_CATEGORY_DEPTH)
        ]

        TagCategory.objects.bulk_create(chain(*tag_category_hierarchy))

        # Populate category parents from children categories upwards
        for i, level in enumerate(tag_category_hierarchy[1:], start=1):
            for category in level:
                category.parent = choice(tag_category_hierarchy[i - 1])

        tag_categories = list(chain(*tag_category_hierarchy))
        TagCategory.objects.bulk_update(tag_categories, fields=["parent"])
    console.print(f"Created {len(tag_categories)} tag categories.")


def create_random_tags(n: int = 500):
    """Create `n` randomized Tags"""
    n = min(n, 10_000)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Creating random tags...", total=None)

        tag_split = 0.5
        simple_random_tag_names = fake.words(int(n * tag_split), unique=True)
        categorized_random_tag_names = fake.words(int(n * (1 - tag_split)), unique=True)

        simple_tags = [
            Tag(name=name, category=None) for name in simple_random_tag_names
        ]
        tags_with_categories = [
            Tag(name=name, category=choice(TagCategory.objects.all()))
            for name in categorized_random_tag_names
        ]
        Tag.tags.bulk_create(simple_tags, ignore_conflicts=True)
        Tag.tags.bulk_create(tags_with_categories, ignore_conflicts=True)
    console.print(f"Created {len(tags_with_categories)} tags.")


def create_random_tag_aliases(tags: QuerySet[Tag], percent: float = 0.1):
    """Create TagAliases for the given set of tags
    percent: percent of Tags to receive an alias
    """

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Creating random tag aliases...", total=None)
        picked_tags = choices(tags, k=int(percent * len(tags)))
        tag_aliases = [
            TagAlias(name=f"alias_{i}_{tag.name}", tag=tag)
            for i, tag in enumerate(picked_tags)
        ]
        TagAlias.aliases.bulk_create(tag_aliases, ignore_conflicts=True)
    console.print(f"Created {len(tag_aliases)} tag aliases.")


def create_random_post_collections(
    posts: QuerySet[Post],
    max_collections: int = 100,
    max_posts_per_collection: int = 50,
):
    """Create collections with randomly assigned posts"""
    collections = []
    collection_posts = []
    user_options = list(User.objects.all())
    post_options = list(posts)
    for _ in range(max_collections):
        collection = Collection(
            user=choice(user_options),
            name=fake.sentence(8),
            desc=fake.sentence(15),
        )
        collections.append(collection)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Creating collections...", total=None)
        created_collections = Collection.objects.bulk_create(collections)

    console.print(f"Created {len(created_collections)} collections.")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Linking collections to posts...", total=None)

        def get_random_post_ids():
            return [
                s.pk
                for s in sample(
                    post_options,
                    k=randint(0, min(max_posts_per_collection, len(post_options))),
                )
            ]

        collection_posts = []
        for collection in created_collections:
            collection_posts.extend(
                [
                    Collection.posts.through(
                        collection_id=collection.pk, post_id=post_id
                    )
                    for post_id in get_random_post_ids()
                ]
            )

        created_collection_posts = Collection.posts.through.objects.bulk_create(
            collection_posts
        )
    console.print(f"Added {len(created_collection_posts)} posts to collections.")


def create_random_user_favorites(
    posts: QuerySet[Post],
    users: QuerySet[User],
    max_favorites_per_user: int = 100,
):
    """Create a random set of favorites for the provided Users, choosing from the list
    of provided Posts"""
    post_options = list(posts)
    fav_count = 0
    favorites = []
    for user in track(users, description="Creating favorites..."):
        selected_posts = sample(
            post_options, k=randint(0, min(max_favorites_per_user, len(post_options)))
        )
        for post in selected_posts:
            fav = Favorite(user=user, post=post)
            favorites.append(fav)
            fav_count += 1

    Favorite.favorites.bulk_create(favorites)
    console.print(f"Created {fav_count} favorites for {len(users)} users.")


def create_random_posts(  # noqa: C901, PLR0912, PLR0915
    media_files: Iterable[Path], user_select_max=100, max_posts=1000
):
    tag_options = list(Tag.tags.all())
    users = User.objects.all()
    uploaders = choices(users, k=user_select_max)
    posts = []
    comments = []
    media_objects = []
    media_files_list = list(media_files)

    media_files_sample = sample(
        media_files_list, k=min(len(media_files_list), max_posts)
    )
    for file in track(
        media_files_sample,
        description="Creating posts from media files...",
    ):
        fp = file.open("rb")
        uploaded_file = UploadedFile(fp)
        magic_mime = magic.from_file(file, mime=True)
        try:
            media_file_supported_validator(uploaded_file)
            uploaded_file = fix_upload_content_type(uploaded_file)
        except ValidationError as err:
            console.print(
                f"File '{file.name}' couldn't be validated because: {err.message}"
            )
            continue

        smt = SupportedMediaType.select_by_mime(magic_mime)
        if smt is None:
            console.print(f"The file type of '{file}' is not supported")
            continue

        post = Post(
            title=fake.sentence(10),
            uploader=choice(uploaders),
            rating_level=choice(RatingLevel.choices)[0],
            src_url=fake.word() + ".example.com",
            type=smt.name,
        )

        comment_texts = [" ".join(fake.sentences(4)) for _ in range(randint(0, 10))]

        comments.extend(
            [
                Comment(post=post, user=choice(users), text=text)
                for text in comment_texts
            ]
        )

        media_object = None
        match smt.value.category:
            case MediaCategory.AUDIO:
                media_object = Audio(file=uploaded_file, orig_name=file.name)
            case MediaCategory.IMAGE:
                try:
                    media_object = Image(file=uploaded_file, orig_name=file.name)
                except UnidentifiedImageError:
                    console.print("The image file couldn't be identified by PIL")
                    console.print(f"See the file at {file.resolve()}")
            case MediaCategory.VIDEO:
                media_object = Video(file=uploaded_file, orig_name=file.name)

        if media_object:
            media_object.post = post
            media_objects.append(media_object)

        posts.append(post)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Creating posts...", total=None)
        created_posts = Post.posts.bulk_create(posts)
    console.print(f"Created {len(created_posts)} posts.")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Adding tags to posts...", total=None)

        post_tags = []

        def get_random_tag_ids():
            return [s.pk for s in sample(tag_options, k=randint(0, 25))]

        for post in created_posts:
            post_tags.extend(
                [
                    Post.tags.through(post_id=post.pk, tag_id=tag_id)
                    for tag_id in get_random_tag_ids()
                ]
            )

        Post.tags.through.objects.bulk_create(post_tags)
    console.print("Tags added to posts.")

    for post in track(created_posts, description="Updating posts' tag histories..."):
        add_tag_history(post.tags.all(), post, post.uploader)

    for post in track(created_posts, description="Updating posts' source histories..."):
        post.save_with_src_history(post.uploader, post.src_url)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Adding comments to posts...", total=None)
        Comment.objects.bulk_create(comments)
    console.print("Comments added to posts.")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Updating tag post counts", total=None)
        update_tag_post_counts()
    console.print("Tag post counts updated.")

    for post in track(
        created_posts, description="Adding parent and child post links..."
    ):
        for child_post in choices(created_posts, k=randint(0, 5)):
            child_post.parent = post
            child_post.save()
    console.print("Parent and child post links added.")

    for obj in track(
        media_objects,
        description="Saving media files to database and generating thumbnails...",
    ):
        try:
            obj.save()
        except OSError as e:
            console.print(e)
            continue
    console.print(f"Saved {len(media_objects)} media files.")


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
