import pytest
from django.contrib.auth.models import Permission

from tesys_tagboard.models import Tag, TagAlias, TagCategory
from tesys_tagboard.users.models import User
from tesys_tagboard.users.tests.factories import UserFactory


# Set faker testing seed for consistent randomized fake data
@pytest.fixture(autouse=True, scope="session")
def faker_seed():
    return 12345


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db) -> User:
    return UserFactory()


@pytest.fixture
def user_with_add_post(db) -> User:
    return UserFactory().with_permissions([Permission.objects.get(codename="add_post")])


@pytest.fixture
def user_with_add_tag(db) -> User:
    return UserFactory().with_permissions([Permission.objects.get(codename="add_tag")])


@pytest.fixture
def user_with_delete_tag(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="delete_tag")]
    )


@pytest.fixture
def user_with_restore_deleted_tags(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="restore_deleted_tags")]
    )


@pytest.fixture
def user_with_add_tagalias(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="add_tagalias")]
    )


@pytest.fixture
def user_with_delete_post(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="delete_post")]
    )


@pytest.fixture
def user_with_change_post(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="change_post")]
    )


@pytest.fixture
def user_with_lock_comments(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="lock_comments")]
    )


@pytest.fixture
def user_with_add_comment(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="add_comment")]
    )


@pytest.fixture
def user_with_change_comment(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="change_comment")]
    )


@pytest.fixture
def user_with_delete_comment(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="delete_comment")]
    )


@pytest.fixture
def user_with_add_collection(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="add_collection")]
    )


@pytest.fixture
def user_with_delete_collection(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="delete_collection")]
    )


@pytest.fixture
def user_with_add_favorite(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="add_favorite")]
    )


@pytest.fixture
def user_with_delete_favorite(db) -> User:
    return UserFactory().with_permissions(
        [Permission.objects.get(codename="delete_favorite")]
    )


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        User.objects.bulk_create(
            [
                User(username="user1", password="user1user1"),  # noqa: S106
                User(username="user2", password="user2user2"),  # noqa: S106
                User(username="user3", password="user3user3"),  # noqa: S106
                User(username="mod1", password="mod1mod1"),  # noqa: S106
                User(username="mod2", password="mod2mod2"),  # noqa: S106
                User(username="mod3", password="mod3mod3"),  # noqa: S106
            ]
        )

        artist_category = TagCategory.objects.get(name__icontains="artist")
        copyright_category = TagCategory.objects.get(name__icontains="copyright")

        continent_category = TagCategory.objects.create(name="continent")
        north_america_category = TagCategory.objects.create(
            name="North_America", parent=continent_category
        )
        south_america_category = TagCategory.objects.create(
            name="South_America", parent=continent_category
        )
        canada_category = TagCategory.objects.create(
            name="Canada", parent=north_america_category
        )
        mexico_category = TagCategory.objects.create(
            name="México", parent=north_america_category
        )
        peru_category = TagCategory.objects.create(
            name="Peru", parent=south_america_category
        )
        brazil_category = TagCategory.objects.create(
            name="Brazil", parent=south_america_category
        )
        lima_territory_category = TagCategory.objects.create(
            name="Lima", parent=brazil_category
        )
        lima_city_category = TagCategory.objects.create(
            name="Lima", parent=lima_territory_category
        )
        cusco_territory_category = TagCategory.objects.create(
            name="Cusco", parent=brazil_category
        )
        cusco_city_category = TagCategory.objects.create(
            name="Cusco", parent=cusco_territory_category
        )

        Tag.tags.bulk_create(
            [
                Tag(name="alabaster"),
                Tag(name="amaranth-pink"),
                Tag(name="amaranth-purple"),
                Tag(name="amaranth"),
                Tag(name="amber"),
                Tag(name="arctic-white"),
                Tag(name="beige"),
                Tag(name="black"),
                Tag(name="blue-jeans"),
                Tag(name="blue"),
                Tag(name="blue-gray"),
                Tag(name="blueberry"),
                Tag(name="brown"),
                Tag(name="crimson"),
                Tag(name="evergreen"),
                Tag(name="green"),
                Tag(name="grey"),
                Tag(name="indigo"),
                Tag(name="lime-green"),
                Tag(name="orange"),
                Tag(name="purple"),
                Tag(name="red"),
                Tag(name="red_vs._blue"),
                Tag(name="sky-blue"),
                Tag(name="violet"),
                Tag(name="violet-hyacinth"),
                Tag(name="white"),
                Tag(name="white-rapids"),
                Tag(name="yellow"),
                Tag(name="yellow-flowers"),
                # Tags in the artist category
                Tag(name="Avery_Luis_Stein", category=artist_category),
                Tag(name="Elif", category=artist_category),
                Tag(name="Garbold_Loop", category=artist_category),
                Tag(name="Justin_Knope", category=artist_category),
                Tag(name="Solomon_Steven", category=artist_category),
                Tag(name="Terry_Toller", category=artist_category),
                Tag(name="Warren_Witt", category=artist_category),
                Tag(name="Yura_Yebolsky", category=artist_category),
                Tag(name="Zammy_Zolan", category=artist_category),
                # Tags in the copyright category
                Tag(name="CC-BY", category=copyright_category),
                Tag(name="MIT", category=copyright_category),
                Tag(name="Public_Domain", category=copyright_category),
                Tag(name="Unlicense", category=copyright_category),
                # Location tags
                Tag(name="Québec", category=canada_category),
                Tag(name="Ontario", category=canada_category),
                Tag(name="Ciudad_de_México", category=mexico_category),
                Tag(name="Monterrey", category=mexico_category),
                Tag(name="Huarez", category=peru_category),
                Tag(name="Pallasca", category=peru_category),
                Tag(name="Dos_de_Mayo", category=peru_category),
                Tag(name="La_Convención", category=cusco_territory_category),
                Tag(name="Qoricancha_Temple", category=cusco_city_category),
                Tag(name="Cristo_Blanco", category=cusco_city_category),
                Tag(name="La_Marina_Lighthouse", category=lima_city_category),
                Tag(name="Basilica_of_Santo_Domingo", category=lima_city_category),
            ]
        )

        TagAlias.aliases.bulk_create(
            [
                TagAlias(name="arctic", tag=Tag.tags.get(name="arctic-white")),
                TagAlias(name="gray", tag=Tag.tags.get(name="grey")),
                TagAlias(name="r_v._b", tag=Tag.tags.get(name="red_vs._blue")),
                TagAlias(name="r_vs._b", tag=Tag.tags.get(name="red_vs._blue")),
                TagAlias(name="red_v._blue", tag=Tag.tags.get(name="red_vs._blue")),
                TagAlias(name="red_vs_blue", tag=Tag.tags.get(name="red_vs._blue")),
                TagAlias(name="red_x_blue", tag=Tag.tags.get(name="red_vs._blue")),
                TagAlias(name="blue-berry", tag=Tag.tags.get(name="blueberry")),
                TagAlias(name="gray-blue", tag=Tag.tags.get(name="blue-gray")),
                TagAlias(name="bluejeans", tag=Tag.tags.get(name="blue-jeans")),
                TagAlias(name="Justin_K", tag=Tag.tags.get(name="Justin_Knope")),
                TagAlias(name="Solomon_S", tag=Tag.tags.get(name="Solomon_Steven")),
                TagAlias(name="Z._Zolan", tag=Tag.tags.get(name="Zammy_Zolan")),
            ]
        )
