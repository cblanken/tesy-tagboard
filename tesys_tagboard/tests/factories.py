import factory
from factory.declarations import Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from faker.providers import BaseProvider

from tesys_tagboard.enums import RatingLevel, SupportedMediaType
from tesys_tagboard.models import (
    Collection,
    Comment,
    Favorite,
    Image,
    Post,
    Tag,
    TagAlias,
    TagCategory,
)
from tesys_tagboard.users.tests.factories import UserFactory


# Add TT-specific providers
class SupportedMediaTypeProvider(BaseProvider):
    supported_media_types = [smt.name for smt in SupportedMediaType]

    def supported_media_type(self):
        return self.random_element(self.supported_media_types)


class ImageSizeProvider(BaseProvider):
    def image_width(self):
        return self.random_int(50, 1000)

    def image_height(self):
        return self.random_int(50, 1000)


Faker.add_provider(SupportedMediaTypeProvider)
Faker.add_provider(ImageSizeProvider)


class TagCategoryFactory(DjangoModelFactory[TagCategory]):
    name = Faker("name")

    class Meta:
        model = TagCategory
        django_get_or_create = ["name"]


class TagFactory(DjangoModelFactory[Tag]):
    name = Sequence(lambda n: f"tag{n}")
    category = None
    deleted = False
    rating_level = Faker("enum", enum_cls=RatingLevel)

    class Meta:
        model = Tag
        django_get_or_create = ["name", "category"]


class TagAliasFactory(DjangoModelFactory[TagAlias]):
    name = Faker("word")
    tag = SubFactory(TagFactory)

    class Meta:
        model = TagAlias
        django_get_or_create = ["name", "tag"]


class PostFactory(DjangoModelFactory[Post]):
    title = Faker("text", max_nb_chars=50)
    uploader = SubFactory(UserFactory)

    rating_level = Faker("enum", enum_cls=RatingLevel)
    src_url = Faker("uri", schemes=["http", "https"])
    locked_comments = False

    type = Faker(SupportedMediaTypeProvider.supported_media_type.__name__)

    class Meta:
        model = Post


class ImageFactory(DjangoModelFactory[Image]):
    post = SubFactory(PostFactory)
    orig_name = Faker("file_name", category="image")
    width = Faker("image_width")
    height = Faker("image_height")
    file = factory.django.ImageField(
        height=factory.SelfAttribute("..height"), width=factory.SelfAttribute("..width")
    )

    class Meta:
        model = Image
        django_get_or_create = ("post",)


class CommentFactory(DjangoModelFactory[Comment]):
    text = Faker("text", max_nb_chars=500)
    post = SubFactory(PostFactory)
    user = SubFactory(UserFactory)

    class Meta:
        model = Comment


class CollectionFactory(DjangoModelFactory[Collection]):
    user = SubFactory(UserFactory)
    name = Faker("text", max_nb_chars=50)
    desc = Faker("text", max_nb_chars=200)

    class Meta:
        model = Collection
        django_get_or_create = ("user", "name")

    @factory.post_generation
    def posts(self, create, extracted, **kwargs):
        if not create or not extracted:
            # Simple build, or nothing to add, do nothing.
            return

        # Add the iterable of groups using bulk addition
        self.posts.add(*extracted)


class FavoriteFactory(DjangoModelFactory[Favorite]):
    post = SubFactory(PostFactory)
    user = SubFactory(UserFactory)

    class Meta:
        model = Favorite
        django_get_or_create = ("user", "post")
