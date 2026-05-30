import pytest

from tesys_tagboard.models import Tag

from .factories import TagFactory

# NOTE: fixtures are defined in tesys_tagboard/conftest.py


@pytest.mark.django_db
class TestLikeLookup:
    def test_like_lookup_start(self):
        tag1 = TagFactory.create(name="abc")
        tag2 = TagFactory.create(name="1abc")
        tag3 = TagFactory.create(name="333abc")
        tag4 = TagFactory.create(name="abcgg")

        tags = Tag.tags.filter(name__like="%abc")
        assert tag1 in tags
        assert tag2 in tags
        assert tag3 in tags
        assert tag4 not in tags

    def test_like_lookup_middle(self):
        tag1 = TagFactory.create(name="abc")
        tag2 = TagFactory.create(name="ab123c")
        tag3 = TagFactory.create(name="a456bc")

        tags = Tag.tags.filter(name__like="ab%c")
        assert tag1 in tags
        assert tag2 in tags
        assert tag3 not in tags

    def test_like_lookup_end(self):
        tag1 = TagFactory.create(name="abc")
        tag2 = TagFactory.create(name="abc123")
        tag3 = TagFactory.create(name="123abc")

        tags = Tag.tags.filter(name__like="abc%")
        assert tag1 in tags
        assert tag2 in tags
        assert tag3 not in tags

    def test_like_lookup_start_middle_end(self):
        tag1 = TagFactory.create(name="START_abc123")
        tag2 = TagFactory.create(name="START_abc_MIDDLE_123")
        tag3 = TagFactory.create(name="123abc_MIDDLE_123_END")
        tag4 = TagFactory.create(name="abc_JUST_MIDDLE_123")
        tag5 = TagFactory.create(name="abc123_JUST_END")
        tag6 = TagFactory.create(name="STARTabMIDDLE123END")
        tag7 = TagFactory.create(name="STARTabcMIDDLE23END")

        tags = Tag.tags.filter(name__like="%abc%123%")
        assert tag1 in tags
        assert tag2 in tags
        assert tag3 in tags
        assert tag4 in tags
        assert tag5 in tags
        assert tag6 not in tags
        assert tag7 not in tags

    def test_wildcard_ignore_comments(self):
        tag1 = TagFactory.create(name="--abc")
        tag2 = TagFactory.create(name="--abc123")
        tag3 = TagFactory.create(name="abc")
        tag4 = TagFactory.create(name="abc123")

        tags = Tag.tags.filter(name__like="--abc%")
        assert tag1 in tags
        assert tag2 in tags
        assert tag3 not in tags
        assert tag4 not in tags


@pytest.mark.django_db(transaction=True)
class TestTagManager:
    def test_soft_delete(self):
        tag = TagFactory.create(name="soft_delete_tag")
        tag.delete()
        tag.refresh_from_db(fields=["deleted"])
        assert tag.deleted

    def test_hard_delete(self):
        tag = TagFactory.create(name="hard_delete_tag")
        tag.delete(hard_delete=True)
        with pytest.raises(Tag.DoesNotExist):
            Tag.tags.get(pk=tag.pk)

    def test_restore_deleted_tag(self):
        tag = TagFactory.create(name="abc", deleted=True)
        assert tag.deleted
        tag.restore()
        assert not tag.deleted
