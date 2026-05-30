from http import HTTPStatus
from mimetypes import types_map
from pathlib import Path

import pytest
from django.contrib.auth.models import Permission
from django.core.files.storage import storages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from tesys_tagboard.enums import MediaCategory, RatingLevel
from tesys_tagboard.models import Collection, Comment, Favorite, Post, Tag, TagAlias
from tesys_tagboard.users.models import User
from tesys_tagboard.users.tests.factories import UserFactory

from .factories import (
    CollectionFactory,
    CommentFactory,
    FavoriteFactory,
    PostFactory,
    TagAliasFactory,
    TagFactory,
)

# NOTE: most fixtures are defined in conftest.py


@pytest.mark.django_db
class TestHomeView:
    url = reverse("home")

    def test_home(self, client):
        response = client.get(self.url)
        assert response.status_code == HTTPStatus.OK
        assertTemplateUsed(response, "pages/home.html")

    def test_max_query_count(self, client):
        client.get(self.url)


@pytest.mark.django_db
class TestTagsView:
    url = reverse("tags")

    def test_tags(self, client):
        response = client.get(self.url)
        assertTemplateUsed(response, "pages/tags.html")
        assert response.status_code == HTTPStatus.OK

    def test_max_query_count(self, client, django_assert_max_num_queries):
        with django_assert_max_num_queries(30):
            client.get(self.url)


@pytest.mark.django_db(transaction=True)
class TestCreateTagView:
    url = reverse("create-tag")

    def test_create_basic_tag_without_perm(self, client):
        """A user without the add_tag permission should not be able to create a tag"""
        user = UserFactory()
        client.force_login(user)
        tag_name = "test_tag_1"

        data = {
            "name": tag_name,
            "rating_level": "0",
        }
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.FORBIDDEN

        with pytest.raises(Tag.DoesNotExist):
            Tag.tags.get(name=tag_name)

    def test_create_basic_tag_with_perm(self, client, user_with_add_tag):
        """The user must have the add_tag permission to create tags"""
        client.force_login(user_with_add_tag)

        tag_count = Tag.tags.all().count()
        tag_name = "test_tag"
        data = {
            "name": tag_name,
            "rating_level": "0",
        }

        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        tag = Tag.tags.get(name=tag_name)
        assert tag.name == tag_name
        assert tag.category is None
        assert tag.rating_level == 0
        new_count = Tag.tags.all().count()
        assert new_count == tag_count + 1

    def test_create_basic_tag_defaults(self, client, user_with_add_tag):
        """Tags created without a category (None) and rating_level of 0 by default"""
        client.force_login(user_with_add_tag)

        tag_name = "test_tag"
        data = {"name": tag_name}

        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        tag = Tag.tags.get(name=tag_name)
        assert tag.name == tag_name
        assert tag.category is None
        assert tag.rating_level == 0

    def test_create_tag_with_invalid_category(self, client, user_with_add_tag):
        """A tag should not be created with an invalid category value"""
        client.force_login(user_with_add_tag)

        tag_name = "test_tag"
        data = {"name": tag_name, "category": "ZZZZZ"}
        response = client.post(self.url, data, follow=True)
        assert response.status_code == HTTPStatus.OK

        with pytest.raises(Tag.DoesNotExist):
            Tag.tags.get(name=tag_name)

    def test_create_tag_with_too_large_rating_level(self, client, user_with_add_tag):
        """A tag should not be created with an invalid category value"""
        client.force_login(user_with_add_tag)

        tag_name = "test_tag"
        data = {"name": tag_name, "rating_level": "999999"}
        response = client.post(self.url, data, follow=True)
        assert response.status_code == HTTPStatus.OK

        with pytest.raises(Tag.DoesNotExist):
            Tag.tags.get(name=tag_name)

    def test_create_tag_with_negative_rating_level(self, client, user_with_add_tag):
        """A tag should not be created with an invalid category value"""
        client.force_login(user_with_add_tag)

        tag_name = "test_tag"
        data = {"name": tag_name, "rating_level": "-1"}
        response = client.post(self.url, data, follow=True)
        assert response.status_code == HTTPStatus.OK

        with pytest.raises(Tag.DoesNotExist):
            Tag.tags.get(name=tag_name)


@pytest.mark.django_db(transaction=True)
class TestCreateTagAliasView:
    url = reverse("create-tag-alias")

    def test_create_basic_tag_alias_without_perm(self, client):
        """A user without the add_tagalias permission should not
        be able to create a tag"""
        user = UserFactory.create()
        client.force_login(user)
        assert not user.has_perm("tesys_tagboard.add_tagalias")
        alias_name = "test_alias_1"
        data = {"name": alias_name, "tag": TagFactory.build()}
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.FORBIDDEN

        with pytest.raises(Tag.DoesNotExist):
            Tag.tags.get(name=alias_name)

    def test_create_basic_tag_alias_with_perm(self, client, user_with_add_tagalias):
        """A user with the add_tagalias permission should be able to create a
        tag alias"""
        client.force_login(user_with_add_tagalias)

        alias_name = "test_alias_1"
        tag = TagFactory.create()
        data = {"name": alias_name, "tag": str(tag.pk)}
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK

        alias = TagAlias.aliases.get(name=alias_name)
        assert alias.name == alias_name
        assert alias.tag == tag

    def test_cannot_create_tag_alias_with_dup_name(
        self, client, user_with_add_tagalias
    ):
        """TagAliases must have a unique name"""
        client.force_login(user_with_add_tagalias)

        duped_alias = TagAliasFactory.create()
        data = {"name": duped_alias.name, "tag": duped_alias.tag.pk}
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        assert TagAlias.aliases.filter(name=duped_alias.name).count() == 1

    def test_tag_alias_create_cannot_edit_alias(self, client, user_with_add_tagalias):
        """The create-tag-alias endpoint should not be able to override an existing
        alias"""
        client.force_login(user_with_add_tagalias)

        before_tag = TagFactory.create()
        before_alias = TagAliasFactory.create(tag=before_tag)
        after_tag = TagFactory.create()
        data = {"name": before_alias.name, "tag": after_tag.pk}
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK

        after_alias = TagAlias.aliases.get(pk=before_alias.pk)
        assert before_alias.tag == after_alias.tag
        assert before_alias.name == after_alias.name


@pytest.mark.django_db
class TestCommenting:
    def add_comment_url(self, pk):
        return reverse("add-post-comment", args=[pk])

    edit_comment_url = reverse("edit-post-comment")
    delete_comment_url = reverse("delete-post-comment")

    def test_add_comment_without_perm(self, client):
        """Users without the `add_comment` permission may not add commennts"""
        post = PostFactory.create()
        user = UserFactory()
        client.force_login(user)
        url = self.add_comment_url(post.pk)
        data = {"text": "testing comment"}
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert post.comment_set.all().count() == 0

    def test_add_comment(self, client, user_with_add_comment):
        post = PostFactory.create()
        client.force_login(user_with_add_comment)
        url = self.add_comment_url(post.pk)
        text = "testing comment"
        data = {"text": text}
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.OK
        assert post.comment_set.filter(text=text).exists()

    def test_add_comment_with_locked_comments(self, client, user_with_add_comment):
        """Comments cannot be added to a post while it's comments are locked"""
        post = PostFactory.create(locked_comments=True)
        client.force_login(user_with_add_comment)
        url = self.add_comment_url(post.pk)
        text = "testing comment"
        data = {"text": text}
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert not post.comment_set.filter(text=text).exists()

    def test_add_too_long_comment(self, client, user_with_add_comment):
        post = PostFactory.create()
        client.force_login(user_with_add_comment)
        url = self.add_comment_url(post.pk)
        text = "A" * 2049
        data = {"text": text}
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
        assert not post.comment_set.filter(text=text).exists()

    def test_add_empty_comment(self, client, user_with_add_comment):
        """Empty comments are not allowed"""
        post = PostFactory.create()
        client.force_login(user_with_add_comment)
        url = self.add_comment_url(post.pk)
        text = ""
        data = {"text": text}
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT

        assert Comment.objects.all().count() == 0
        assert not post.comment_set.filter(text=text).exists()

    def test_add_whitespace_comment(self, client, user_with_add_comment):
        """Empty comments with only whitespace are not allowed"""
        post = PostFactory.create()
        client.force_login(user_with_add_comment)

        text = "   \n"
        data = {"text": text}
        url = self.add_comment_url(post.pk)
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT

        assert Comment.objects.all().count() == 0
        assert not post.comment_set.filter(text=text).exists()

    def test_edit_comment_without_perm(self, client):
        """User's without the change_comment permission may not edit comments"""
        user = UserFactory()
        post = PostFactory.create()
        comment = CommentFactory.create(post=post)
        client.force_login(user)

        text = "testing text"
        assert text != comment.text
        data = {"text": text, "comment_id": comment.pk}
        url = self.edit_comment_url
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FORBIDDEN

        assert post.comment_set.filter(text=comment.text).exists()
        assert not post.comment_set.filter(text=text).exists()

    def test_edit_comment_of_another_user(self, client, user_with_change_comment):
        """User's may not edit other users' comments, even if they have the
        change_post permission"""
        post = PostFactory.create()
        other_user = UserFactory()
        comment = CommentFactory.create(post=post, user=other_user)
        client.force_login(user_with_change_comment)
        url = self.edit_comment_url

        text = "testing text"
        assert text != comment.text
        data = {"text": text, "comment_id": comment.pk}
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FORBIDDEN

        assert post.comment_set.filter(text=comment.text).exists()
        assert not post.comment_set.filter(text=text).exists()

    def test_edit_comment(self, client, user_with_change_comment):
        """A User with the change_comment permission may edit their own comments"""
        post = PostFactory.create()
        comment = CommentFactory.create(post=post, user=user_with_change_comment)
        client.force_login(user_with_change_comment)

        url = self.edit_comment_url
        text = "testing comment text here"
        data = {"text": text, "comment_id": comment.pk}
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.OK
        comment.refresh_from_db()
        assert comment.text == text

    def test_delete_comment_without_perm(self, client):
        """A User without the delete_comment permission may not delete comments, not
        even their own comments."""
        post = PostFactory.create()
        user = UserFactory()
        comment = CommentFactory.create(post=post, user=user)
        client.force_login(user)

        url = self.delete_comment_url
        data = {"comment_id": comment.pk}
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert Comment.objects.filter(pk=comment.pk).exists()

    def test_delete_comment_of_another_user(self, client, user_with_delete_comment):
        """User's may not delete other users' comments, even if they have the
        delete_comment permission"""
        post = PostFactory.create()
        other_user = UserFactory()
        comment = CommentFactory.create(post=post, user=other_user)
        client.force_login(user_with_delete_comment)

        url = self.delete_comment_url
        data = {"comment_id": comment.pk}
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert Comment.objects.filter(pk=comment.pk).exists()

    def test_delete_comment(self, client, user_with_delete_comment):
        """A User with the delete_comment permission may delete their own comments"""
        post = PostFactory.create()
        comment = CommentFactory.create(post=post, user=user_with_delete_comment)
        client.force_login(user_with_delete_comment)

        url = self.delete_comment_url
        data = {"comment_id": comment.pk}
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.OK
        assert not Comment.objects.filter(pk=comment.pk).exists()


@pytest.mark.django_db
class TestPostView:
    def view_url(self, pk):
        return reverse("post", args=[pk])

    def edit_url(self, pk):
        return reverse("edit-post", args=[pk])

    def delete_url(self, pk):
        return reverse("delete-post", args=[pk])

    def lock_comments_url(self, pk):
        return reverse("toggle-post-comment-lock", args=[pk])

    def test_view_post(self, client):
        post = PostFactory.create()
        url = self.view_url(post.pk)
        response = client.get(url)
        assert response.status_code == HTTPStatus.OK

    def test_delete_post_without_perm(self, client):
        """Users without the `delete_post` permission may not delete posts"""
        post = PostFactory.create()
        user = UserFactory()
        client.force_login(user)

        url = self.delete_url(post.pk)
        response = client.delete(url)
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert Post.posts.filter(pk=post.pk).exists()

    def test_delete_post_with_perm(self, client, user_with_delete_post):
        """Users with the `delete_post` permission may delete posts"""
        post = PostFactory.create()
        client.force_login(user_with_delete_post)

        url = self.delete_url(post.pk)
        response = client.delete(url)
        assert response.status_code == HTTPStatus.FOUND
        assert not Post.posts.filter(pk=post.pk).exists()

    def test_edit_post_only_title(self, client, user_with_change_post):
        post = PostFactory.create()
        client.force_login(user_with_change_post)

        before_src_url = post.src_url
        before_rating_level = post.rating_level
        before_tagset = post.tagset()
        before_locked_comments = post.locked_comments

        new_title = "new title here"
        assert post.title != new_title
        data = {"title": new_title}
        url = self.edit_url(post.pk)
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FOUND
        post.refresh_from_db()
        assert post.title == new_title
        assert post.src_url == before_src_url
        assert post.tagset() == before_tagset
        assert post.rating_level == before_rating_level
        assert post.locked_comments == before_locked_comments

    def test_edit_post_only_rating_level(self, client, user_with_change_post):
        post = PostFactory.create(rating_level=RatingLevel.SAFE.value)
        client.force_login(user_with_change_post)

        before_title = post.title
        before_src_url = post.src_url
        before_tagset = post.tagset()
        before_locked_comments = post.locked_comments

        new_rating_level = RatingLevel.EXPLICIT.value
        assert post.rating_level != new_rating_level
        data = {"rating_level": new_rating_level}
        url = self.edit_url(post.pk)
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FOUND
        post.refresh_from_db()
        assert post.title == before_title
        assert post.src_url == before_src_url
        assert post.tagset() == before_tagset
        assert post.rating_level == new_rating_level
        assert post.locked_comments == before_locked_comments

    def test_edit_post_only_src_url(self, client, user_with_change_post):
        post = PostFactory.create(src_url="https://old-url.com")
        client.force_login(user_with_change_post)

        before_title = post.title
        before_rating_level = post.rating_level
        before_tagset = post.tagset()
        before_locked_comments = post.locked_comments

        new_src_url = "https://new-url.com"
        assert post.src_url != new_src_url
        data = {"src_url": new_src_url}
        url = self.edit_url(post.pk)
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FOUND
        post.refresh_from_db()
        assert post.title == before_title
        assert post.src_url == new_src_url
        assert post.tagset() == before_tagset
        assert post.rating_level == before_rating_level
        assert post.locked_comments == before_locked_comments

    def test_edit_post_only_tags(self, client, user_with_change_post):
        post = PostFactory.create()
        old_tags = TagFactory.create_batch(10)
        post.tags.set(old_tags)
        client.force_login(user_with_change_post)

        before_title = post.title
        before_rating_level = post.rating_level
        before_src_url = post.src_url
        before_locked_comments = post.locked_comments

        new_tags = TagFactory.create_batch(10)
        new_tagset = {tag.pk for tag in new_tags}
        assert post.tagset() != new_tagset
        data = {"tagset": new_tagset}
        url = self.edit_url(post.pk)
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FOUND
        post.refresh_from_db()
        assert post.title == before_title
        assert post.src_url == before_src_url
        assert post.tagset() == new_tagset
        assert post.rating_level == before_rating_level
        assert post.locked_comments == before_locked_comments

    def test_edit_post_all_fields(self, client, user_with_change_post):
        post = PostFactory.create(
            title="old title here",
            src_url="https://www.old-url.com",
            rating_level=RatingLevel.SAFE.value,
        )
        client.force_login(user_with_change_post)

        tags = TagFactory.create_batch(10)

        title = "new title here"
        src_url = "https://www.new-url-here.com"
        tag_ids = [tag.pk for tag in tags]
        rating_level = RatingLevel.EXPLICIT.value
        data = {
            "title": title,
            "src_url": src_url,
            "tagset": tag_ids,
            "rating_level": rating_level,
        }
        url = self.edit_url(post.pk)
        response = client.post(url, data)
        assert response.status_code == HTTPStatus.FOUND
        post.refresh_from_db()
        assert post.title == title
        assert post.src_url == src_url
        assert set(post.tags.values_list("pk", flat=True)) == set(tag_ids)
        assert post.rating_level == rating_level

    @pytest.mark.parametrize("initial", [True, False])
    def test_lock_unlock_comments_with_perm(self, client, initial):
        post = PostFactory.create(locked_comments=initial)
        user = UserFactory().with_permissions(
            [
                Permission.objects.get(codename="change_post"),
                Permission.objects.get(codename="lock_comments"),
            ]
        )
        client.force_login(user)
        url = self.lock_comments_url(post.pk)

        response = client.post(url)
        assert response.status_code == HTTPStatus.OK
        post.refresh_from_db()
        assert post.locked_comments != initial

    @pytest.mark.parametrize("initial", [True, False])
    def test_lock_unlock_comments_without_perm(self, client, initial):
        post = PostFactory.create(locked_comments=initial)
        user = UserFactory()
        client.force_login(user)
        url = self.lock_comments_url(post.pk)

        response = client.post(url)
        assert response.status_code == HTTPStatus.FORBIDDEN
        post.refresh_from_db()
        assert post.locked_comments == initial


@pytest.mark.django_db
class TestPostsView:
    url = reverse("posts")

    def test_posts(self, client):
        response = client.get(self.url)
        assert response.status_code == HTTPStatus.OK
        assertTemplateUsed(response, "pages/posts.html")

    def test_max_query_count(self, client, django_assert_max_num_queries):
        with django_assert_max_num_queries(20):
            client.get(self.url)

    def test_max_logged_in_query_count(self, client, django_assert_max_num_queries):
        user = User.objects.get(username="user1")
        client.force_login(user)
        with django_assert_max_num_queries(25):
            client.get(self.url)


@pytest.mark.django_db
class TestPostsAutocomplete:
    url = reverse("autocomplete")

    def test_autocomplete_as_anonymous_user(self, client):
        data = {"query": "blu"}
        response = client.get(self.url, data)
        assert response.status_code == HTTPStatus.OK

    def test_autocomplete_as_known_user(self, client):
        user = UserFactory.create()
        client.force_login(user)
        data = {"query": "blu"}
        response = client.get(self.url, data)
        assert response.status_code == HTTPStatus.OK


def get_uploaded_test_media_file(
    filename: str, ext: str, *, cat: MediaCategory = MediaCategory.IMAGE
):
    ext = f".{ext}" if ext[0] != "." else ext
    store = storages["test-media"]
    match cat:
        case MediaCategory.IMAGE:
            file = Path(store.path(f"images/{filename}{ext}"))
        case MediaCategory.AUDIO:
            file = Path(store.path(f"audios/{filename}{ext}"))
        case MediaCategory.VIDEO:
            file = Path(store.path(f"videos/{filename}{ext}"))

    if content_type := types_map.get(ext):
        return SimpleUploadedFile(
            filename,
            file.read_bytes(),
            content_type=content_type,
        )
    msg = "Invalid file or extension provided."
    raise ValueError(msg)


@pytest.mark.django_db
class TestUploadView:
    url = reverse("upload")

    def test_upload_anonymous(self, client):
        response = client.get(self.url, follow=True)
        assert response.redirect_chain[0][0] == "/accounts/login/?next=/upload/"
        assert response.status_code == HTTPStatus.OK
        assertTemplateUsed(response, "account/login.html")

    def test_max_query_count(self, client, django_assert_max_num_queries):
        with django_assert_max_num_queries(20):
            client.get(self.url)

    def test_user_without_add_post_perm(self, client):
        """User's without the 'add_post' permission cannot make posts"""
        user = UserFactory()
        client.force_login(user)

        img_file = get_uploaded_test_media_file("1x1", "png")
        data = {"file": img_file}

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.FORBIDDEN
        after_posts = Post.posts.all().count()

        assert after_posts == before_posts

    def test_create_post_with_title(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "png")
        title_text = "Happy Titley Title Here"
        data = {"title": title_text, "file": img_file}

        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        assert Post.posts.filter(title=title_text).exists()

    def test_create_post_with_too_long_title(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "png")
        title_text = "A " * 501  # 1002 character long title
        data = {"title": title_text, "file": img_file}

        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
        assert not Post.posts.filter(title=title_text).exists()

    def test_create_png_img_post(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "png")
        data = {"file": img_file}

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        after_posts = Post.posts.all().count()

        assert after_posts == before_posts + 1

    def test_create_jpg_img_post(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "jpeg")
        data = {"file": img_file}

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        after_posts = Post.posts.all().count()

        assert after_posts == before_posts + 1

    def test_create_webp_img_post(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "webp")
        data = {"file": img_file}

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        after_posts = Post.posts.all().count()

        assert after_posts == before_posts + 1

    def test_create_tiff_img_post(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "tif")
        data = {"file": img_file}

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        after_posts = Post.posts.all().count()

        assert after_posts == before_posts + 1

    def test_create_gif_img_post(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "gif")
        data = {"file": img_file}

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        after_posts = Post.posts.all().count()

        assert after_posts == before_posts + 1

    def test_create_mp3_audio_post(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        audio_file = get_uploaded_test_media_file("1s", "mp3", cat=MediaCategory.AUDIO)
        data = {"file": audio_file}

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        after_posts = Post.posts.all().count()

        assert after_posts == before_posts + 1

    def test_create_wav_audio_post(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        audio_file = get_uploaded_test_media_file("1s", "wav", cat=MediaCategory.AUDIO)
        data = {"file": audio_file}

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        after_posts = Post.posts.all().count()

        assert after_posts == before_posts + 1

    def test_create_webm_video_post(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        video_file = get_uploaded_test_media_file("1s", "webm", cat=MediaCategory.VIDEO)
        data = {"file": video_file}

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        after_posts = Post.posts.all().count()

        assert after_posts == before_posts + 1

    def test_create_mpeg_video_post(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        video_file = get_uploaded_test_media_file("1s", "mpg", cat=MediaCategory.VIDEO)
        data = {"file": video_file}

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        after_posts = Post.posts.all().count()

        assert after_posts == before_posts + 1

    def test_create_post_with_tags(self, client, user_with_add_post):
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "png")
        tags = TagFactory.create_batch(10)
        tag_ids = [tag.pk for tag in tags]
        data = {"file": img_file, "tagset": tag_ids}

        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK

        post = Post.posts.filter(tags__in=tag_ids).distinct().first()
        assert set(tag_ids) == set(post.tags.values_list("pk", flat=True))

    def test_create_post_with_tags_src_and_rating(self, client, user_with_add_post):
        """Post should set all provided fields correctly"""
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "png")
        tags = TagFactory.create_batch(10)
        tag_ids = [tag.pk for tag in tags]
        data = {
            "file": img_file,
            "tagset": tag_ids,
            "src_url": "https://www.example.com",
            "rating_level": RatingLevel.SAFE.value,
        }

        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK

        post = Post.posts.filter(tags__in=tag_ids).distinct().first()
        assert set(tag_ids) == set(post.tags.values_list("pk", flat=True))
        assert post.rating_level == RatingLevel.SAFE.value
        assert post.src_url == "https://www.example.com"

    def test_create_post_with_invalid_src_url(self, client, user_with_add_post):
        """Post should not be created when provided with an invalid src url"""
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "png")
        tags = TagFactory.create_batch(10)
        tag_ids = [tag.pk for tag in tags]
        data = {
            "file": img_file,
            "tagset": tag_ids,
            "src_url": "nope://www.example.com",
            "rating_level": RatingLevel.SAFE.value,
        }

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
        after_posts = Post.posts.all().count()
        assert after_posts == before_posts

    def test_create_post_with_invalid_rating_level(self, client, user_with_add_post):
        """Post should not be created when provided with an invalid rating level"""
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "png")
        data = {
            "file": img_file,
            "rating_level": 99999,
        }

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
        after_posts = Post.posts.all().count()
        assert after_posts == before_posts

    def test_create_post_with_invalid_tag_ids(self, client, user_with_add_post):
        """Post request may include invalid tag IDs, they just won't be included
        on the new Post"""
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "png")
        tags = TagFactory.create_batch(10)
        tag_ids = [tag.pk for tag in tags]
        bad_ids = [1111, 2222, 3333, 4444, 5555]
        tag_ids.extend(bad_ids)
        data = {
            "file": img_file,
            "tagset": tag_ids,
        }

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.OK
        after_posts = Post.posts.all().count()
        assert after_posts == before_posts + 1

    def test_create_post_with_invalid_tag_values(self, client, user_with_add_post):
        """Post request may not include non-integer values"""
        client.force_login(user_with_add_post)

        img_file = get_uploaded_test_media_file("1x1", "png")
        tags = TagFactory.create_batch(10)
        tag_ids = [tag.pk for tag in tags]
        bad_ids = ["abc", 2, 3, 4, 5]
        tag_ids.extend(bad_ids)
        data = {
            "file": img_file,
            "tagset": tag_ids,
        }

        before_posts = Post.posts.all().count()
        response = client.post(self.url, data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
        after_posts = Post.posts.all().count()
        assert after_posts == before_posts


@pytest.mark.django_db
class TestFavorites:
    def add_url(self, post_id):
        return reverse("add-favorite", args=[post_id])

    def delete_url(self, post_id):
        return reverse("remove-favorite", args=[post_id])

    def test_add_favorite_without_perm(self, client):
        """Users without the add_favorite permission may not create favorites"""
        user = UserFactory()
        client.force_login(user)
        post = PostFactory.create()
        response = client.put(self.add_url(post.pk))
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert not Favorite.favorites.filter(post=post, user=user).exists()

    def test_add_favorite(self, client, user_with_add_favorite):
        """Users with the add_favorite permission may create new favorites for
        themselves"""
        client.force_login(user_with_add_favorite)
        post = PostFactory.create()
        client.put(self.add_url(post.pk))
        assert Favorite.favorites.filter(
            post=post, user=user_with_add_favorite
        ).exists()

    def test_add_multiple_favorites(self, client, user_with_add_favorite):
        """Users with the add_favorite permission may create multiple new favorites for
        themselves"""
        client.force_login(user_with_add_favorite)
        posts = PostFactory.create_batch(10)
        for post in posts:
            response = client.put(self.add_url(post.pk))
            assert response.status_code == HTTPStatus.OK

        for post in posts:
            assert Favorite.favorites.filter(
                post=post, user=user_with_add_favorite
            ).exists()

    def test_add_favorite_with_invalid_post_id(self, client, user_with_add_favorite):
        """Requests to add a favorite with a non-existant Post should return an error"""
        client.force_login(user_with_add_favorite)
        bad_id = 9999
        response = client.put(self.add_url(bad_id))
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert not Favorite.favorites.filter(
            post__pk=bad_id, user=user_with_add_favorite
        ).exists()

    def test_delete_favorite_without_perm(self, client):
        """Users without the delete_favorite permission may not delete favorites"""
        user = UserFactory()
        client.force_login(user)
        favorite = FavoriteFactory.create()
        response = client.put(self.delete_url(favorite.post.pk))
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert Favorite.favorites.filter(
            post=favorite.post, user=favorite.user
        ).exists()

    def test_delete_favorite(self, client, user_with_delete_favorite):
        """Users with the delete_favorite permission may delete their own favorites"""
        client.force_login(user_with_delete_favorite)
        favorite = FavoriteFactory(user=user_with_delete_favorite)
        response = client.put(self.delete_url(favorite.post.pk))
        assert response.status_code == HTTPStatus.OK
        assert not Favorite.favorites.filter(
            post=favorite.post, user=favorite.user
        ).exists()


@pytest.mark.django_db
class TestCollections:
    view_url = reverse("collections")
    create_url = reverse("create-collection")

    def delete_url(self, collection_id: int):
        return reverse("delete-collection", args=[collection_id])

    def test_collections(self, client):
        response = client.get(self.view_url)
        assert response.status_code == HTTPStatus.OK
        assertTemplateUsed(response, "pages/collections.html")

    def test_max_query_count(self, client, django_assert_max_num_queries):
        with django_assert_max_num_queries(20):
            client.get(self.view_url)

    def test_create_collection_without_perm(self, client):
        """Users without the add_collection permission may not create
        new collections"""
        user = UserFactory()
        client.force_login(user)
        name = "collection name here"
        data = {
            "name": name,
            "desc": "description for this collection",
        }
        response = client.post(self.create_url, data)
        assert response.status_code == HTTPStatus.FORBIDDEN
        with pytest.raises(Collection.DoesNotExist):
            Collection.objects.get(name=name)

    def test_create_collection(self, client, user_with_add_collection):
        """Users with the add_collection permission may create new collections
        for themselves"""
        client.force_login(user_with_add_collection)
        name = "normal collection"
        data = {
            "name": name,
            "desc": "description for this collection",
        }
        response = client.post(self.create_url, data)
        assert response.status_code == HTTPStatus.OK
        assert Collection.objects.filter(
            name=name, user=user_with_add_collection
        ).exists()

    def test_create_collection_with_too_long_name(
        self, client, user_with_add_collection
    ):
        """Collection names may not be *too* long"""
        client.force_login(user_with_add_collection)
        too_long_name = "A" * 150
        data = {
            "name": too_long_name,
            "desc": "description for this collection",
        }
        response = client.post(self.create_url, data)
        assert response.status_code == HTTPStatus.OK
        assert not Collection.objects.filter(name=too_long_name).exists()

    def test_create_collection_with_empty_name(self, client, user_with_add_collection):
        """Collection name may not be empty string"""
        client.force_login(user_with_add_collection)
        empty_name = ""
        data = {
            "name": empty_name,
            "desc": "description for this collection",
        }
        response = client.post(self.create_url, data)
        assert response.status_code == HTTPStatus.OK
        assert not Collection.objects.filter(name=empty_name).exists()

    def test_create_collection_with_too_long_description(
        self, client, user_with_add_collection
    ):
        """Collection names may not be *too* long"""
        client.force_login(user_with_add_collection)
        too_long_desc = "A" * 1000
        data = {
            "name": "normal collection name",
            "desc": too_long_desc,
        }
        client.post(self.create_url, data)
        assert not Collection.objects.filter(desc=too_long_desc).exists()

    def test_delete_collection_without_perm(self, client):
        """Collections may not be deleted without the required permission"""
        user = UserFactory()
        client.force_login(user)
        collection = CollectionFactory.create()
        response = client.delete(self.delete_url(collection.pk))
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert Collection.objects.filter(pk=collection.pk).exists()

    def test_delete_collection(self, client, user_with_delete_collection):
        """Users may delete their *own* collections"""
        client.force_login(user_with_delete_collection)
        collection = CollectionFactory.create(user=user_with_delete_collection)
        response = client.delete(self.delete_url(collection.pk))
        assert response.status_code == HTTPStatus.OK
        assert not Collection.objects.filter(pk=collection.pk).exists()

    def test_delete_collection_of_another_user(
        self, client, user_with_delete_collection
    ):
        """Users may not delete collections of other users"""
        user = UserFactory()
        client.force_login(user_with_delete_collection)
        collection = CollectionFactory.create(user=user)
        response = client.delete(self.delete_url(collection.pk))
        assert response.status_code == HTTPStatus.OK
        assert Collection.objects.filter(pk=collection.pk).exists()

    def test_add_post_to_collection(self, client):
        """Users may add posts to their own collections"""
        user = UserFactory.create().with_permissions(
            [Permission.objects.get(codename="add_post_to_collection")]
        )
        post = PostFactory.create()
        collection = CollectionFactory.create(user=user)
        url = reverse("collection-add-post", args=[collection.pk])

        client.force_login(user)
        resp = client.post(url, {"post": post.pk})
        assert resp.status_code == HTTPStatus.OK
        assert collection.posts.filter(pk=post.pk).exists()

    def test_add_post_to_collection_without_perm(self, client):
        """Users may add posts to their own collections"""
        user = UserFactory.create()
        post = PostFactory.create()
        collection = CollectionFactory.create(user=user)
        url = reverse("collection-add-post", args=[collection.pk])

        client.force_login(user)
        resp = client.post(url, {"post": post.pk})
        assert resp.status_code == HTTPStatus.FORBIDDEN
        assert not collection.posts.filter(pk=post.pk).exists()

    def test_remove_post_from_collection(self, client):
        """Users may remove posts from their own collections"""
        user = UserFactory.create().with_permissions(
            [Permission.objects.get(codename="remove_post_from_collection")]
        )
        posts = PostFactory.create_batch(10)
        collection = CollectionFactory.create(user=user)
        collection.posts.set(posts)

        client.force_login(user)
        removed_post = posts[0]
        url = reverse("collection-remove-post", args=[collection.pk])
        resp = client.post(url, {"post": removed_post.pk})
        assert resp.status_code == HTTPStatus.OK
        assert not collection.posts.filter(pk=removed_post.pk).exists()

        # Ensure all remaining posts still exist in collection
        for post in posts[1:]:
            assert collection.posts.filter(pk=post.pk).exists()

    def test_remove_post_from_collection_without_perm(self, client):
        """Users may not remove posts from any collections without the remove perm"""
        user = UserFactory.create()
        posts = PostFactory.create_batch(10)
        collection = CollectionFactory.create(user=user)
        collection.posts.set(posts)

        client.force_login(user)
        removed_post = posts[0]
        url = reverse("collection-remove-post", args=[collection.pk])
        resp = client.post(url, {"post": removed_post.pk})
        assert resp.status_code == HTTPStatus.FORBIDDEN

        # Ensure all remaining posts still exist in collection
        for post in posts[1:]:
            assert collection.posts.filter(pk=post.pk).exists()


@pytest.mark.django_db
class TestHelpView:
    url = reverse("help")

    def test_help(self, client):
        response = client.get(self.url)
        assert response.status_code == HTTPStatus.OK
        assertTemplateUsed(response, "pages/help.html")

    def test_max_query_count(self, client, django_assert_max_num_queries):
        with django_assert_max_num_queries(20):
            client.get(self.url)
