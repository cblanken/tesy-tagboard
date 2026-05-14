"""Test module for simple (single token type) filters"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from tesys_tagboard.enums import RatingLevel, SupportedMediaType
from tesys_tagboard.models import Post
from tesys_tagboard.search import TAG_CATEGORY_DELIMITER, PostSearch
from tesys_tagboard.tests.factories import (
    CollectionFactory,
    CommentFactory,
    FavoriteFactory,
    ImageFactory,
    PostFactory,
    TagAliasFactory,
    TagCategoryFactory,
    TagFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestSearchTags:
    def test_empty_query(self):
        PostFactory.create_batch(10)
        ps = PostSearch("")
        posts = ps.get_posts()
        assert len(posts.difference(Post.posts.all())) == 0

    def test_only_include_tags(self):
        common_tag = TagFactory.create()

        included_posts = PostFactory.create_batch(10)
        included_tag = TagFactory.create()
        for post in included_posts:
            post.tags.add(included_tag)
            post.tags.add(common_tag)

        not_included_posts = PostFactory.create_batch(10)
        not_included_tag = TagFactory.create()
        for post in not_included_posts:
            post.tags.add(not_included_tag)
            post.tags.add(common_tag)

        ps = PostSearch(f"{included_tag.name}")
        posts = ps.get_posts()
        assert len(posts.difference(Post.posts.filter(tags__in=[included_tag]))) == 0
        assert len(
            posts.difference(Post.posts.filter(tags__in=[not_included_tag]))
        ) == len(not_included_posts)

    def test_include_tag_with_category(self):
        common_tag = TagFactory.create()

        # Posts to be included in results
        category = TagCategoryFactory.create(name="category1")
        included_posts = PostFactory.create_batch(5)
        included_tag = TagFactory.create(category=category)
        for post in included_posts:
            post.tags.add(included_tag)
            post.tags.add(common_tag)

        # Posts not to be included in results
        not_included_posts = PostFactory.create_batch(5)
        not_included_tag = TagFactory.create()
        for post in not_included_posts:
            post.tags.add(not_included_tag)
            post.tags.add(common_tag)

        query = TAG_CATEGORY_DELIMITER.join(
            [included_tag.category.name, included_tag.name]
        )
        ps = PostSearch(query)
        posts = ps.get_posts()
        assert len(posts.difference(Post.posts.filter(tags__in=[included_tag]))) == 0
        assert len(
            posts.difference(Post.posts.filter(tags__in=[not_included_tag]))
        ) == len(not_included_posts)

    def test_include_tag_with_nested_categories(self):
        common_tag = TagFactory.create()

        # Posts to be included in results
        category1 = TagCategoryFactory.create(name="category1")
        category2 = TagCategoryFactory.create(name="category2", parent=category1)
        included_posts = PostFactory.create_batch(5)
        included_tag = TagFactory.create(category=category2)
        for post in included_posts:
            post.tags.add(included_tag)
            post.tags.add(common_tag)

        # Posts not to be included in results
        not_included_posts = PostFactory.create_batch(5)
        not_included_tag = TagFactory.create()
        for post in not_included_posts:
            post.tags.add(not_included_tag)
            post.tags.add(common_tag)

        query = TAG_CATEGORY_DELIMITER.join(
            [
                included_tag.category.parent.name,
                included_tag.category.name,
                included_tag.name,
            ]
        )
        ps = PostSearch(query)
        posts = ps.get_posts()
        assert len(posts.difference(Post.posts.filter(tags__in=[included_tag]))) == 0
        assert len(
            posts.difference(Post.posts.filter(tags__in=[not_included_tag]))
        ) == len(not_included_posts)

    def test_exclude_tag_with_category(self):
        tags = TagFactory.create_batch(5)
        test_posts = PostFactory.create_batch(5)

        category = TagCategoryFactory.create(name="cat1")
        tags[0].category = category
        tags[0].save()

        for i, post in enumerate(test_posts):
            post.tags.add(tags[i])

        posts = PostSearch(
            f"-{tags[0].category.name}{TAG_CATEGORY_DELIMITER}{tags[0].name}"
        ).get_posts()
        assert test_posts[0] not in posts
        assert test_posts[1] in posts
        assert test_posts[2] in posts
        assert test_posts[3] in posts
        assert test_posts[4] in posts

    def test_exclude_tag_with_nested_categories(self):
        tags = TagFactory.create_batch(5)
        test_posts = PostFactory.create_batch(5)

        category1 = TagCategoryFactory.create(name="cat1")
        category2 = TagCategoryFactory.create(name="cat2", parent=category1)
        tags[0].category = category2
        tags[0].save()

        for i, post in enumerate(test_posts):
            post.tags.add(tags[i])

        query = "-" + TAG_CATEGORY_DELIMITER.join(
            [tags[0].category.parent.name, tags[0].category.name, tags[0].name]
        )
        posts = PostSearch(query).get_posts()
        assert test_posts[0] not in posts
        assert test_posts[1] in posts
        assert test_posts[2] in posts
        assert test_posts[3] in posts
        assert test_posts[4] in posts

    def test_include_tag_with_wildcard(self):  # noqa: PLR0915
        wild = TagFactory.create(name="wild")
        wilder = TagFactory.create(name="wilder")
        wilderness = TagFactory.create(name="wilderness")
        ness = TagFactory.create(name="ness")
        dress = TagFactory.create(name="dress")
        bless = TagFactory.create(name="bless")

        just_wild_post = PostFactory.create()
        just_wild_post.tags.add(wild)

        all_wild_post = PostFactory.create()
        all_wild_post.tags.add(wild, wilder, wilderness)

        all_wilder_post = PostFactory.create()
        all_wilder_post.tags.add(wilder, wilderness)

        just_wilderness_post = PostFactory.create()
        just_wilderness_post.tags.add(wilderness)

        ess_post = PostFactory.create()
        ess_post.tags.add(ness, dress, bless)

        ness_post = PostFactory.create()
        ness_post.tags.add(wilderness, ness)

        bless_post = PostFactory.create()
        bless_post.tags.add(bless)

        wild_ps = PostSearch("wild*")
        wild_posts = wild_ps.get_posts()
        assert just_wild_post in wild_posts
        assert all_wild_post in wild_posts
        assert all_wilder_post in wild_posts
        assert just_wilderness_post in wild_posts
        assert ness_post in wild_posts
        assert ess_post not in wild_posts

        wilder_ps = PostSearch("wilder*")
        wilder_posts = wilder_ps.get_posts()
        assert all_wild_post in wilder_posts
        assert all_wilder_post in wilder_posts
        assert just_wilderness_post in wilder_posts
        assert ness_post in wilder_posts
        assert just_wild_post not in wilder_posts

        wilderness_ps = PostSearch("wilderness*")
        wilderness_posts = wilderness_ps.get_posts()
        assert all_wild_post in wilderness_posts
        assert all_wilder_post in wilderness_posts
        assert just_wilderness_post in wilderness_posts
        assert ness_post in wilderness_posts
        assert just_wild_post not in wilderness_posts

        ess_ps = PostSearch("*ess")
        ess_posts = ess_ps.get_posts()
        assert ess_post in ess_posts
        assert ness_post in ess_posts
        assert bless_post in ess_posts
        assert just_wilderness_post in ess_posts
        assert just_wild_post not in ess_posts

        ness_ps = PostSearch("*ness")
        ness_posts = ness_ps.get_posts()
        assert ess_post in ness_posts
        assert ness_post in ness_posts
        assert just_wilderness_post in ness_posts
        assert bless_post not in ness_posts
        assert just_wild_post not in ness_posts

    def test_only_exclude_tags(self):
        tags = TagFactory.create_batch(5)
        test_posts = PostFactory.create_batch(5)

        for i, post in enumerate(test_posts):
            post.tags.add(tags[i])

        posts = PostSearch(f"-{tags[0].name} -{tags[1].name}").get_posts()
        assert test_posts[0] not in posts
        assert test_posts[1] not in posts
        assert test_posts[2] in posts
        assert test_posts[3] in posts
        assert test_posts[4] in posts

    def test_exclude_tag_with_wildcard(self):
        common_tag = TagFactory.create(name="mighty")
        tags = TagFactory.create_batch(5)
        test_posts = PostFactory.create_batch(5)

        for i, post in enumerate(test_posts):
            post.tags.add(common_tag, tags[i])

        wildcard_tag = TagFactory.create(name="mire")
        test_posts[0].tags.add(wildcard_tag)
        test_posts[1].tags.add(wildcard_tag)
        test_posts[2].tags.add(wildcard_tag)

        posts = PostSearch("-mir*").get_posts()
        assert test_posts[0] not in posts
        assert test_posts[1] not in posts
        assert test_posts[2] not in posts
        assert test_posts[3] in posts
        assert test_posts[4] in posts

    def test_include_and_exclude_tags_with_wildcards(self):
        common_tag = TagFactory.create(name="mighty")
        tags = TagFactory.create_batch(5)
        test_posts = PostFactory.create_batch(5)

        for i, post in enumerate(test_posts):
            post.tags.add(common_tag, tags[i])

        wildcard_tag = TagFactory.create(name="mire")
        test_posts[0].tags.add(wildcard_tag)
        test_posts[1].tags.add(wildcard_tag)
        test_posts[2].tags.add(wildcard_tag)

        special_tag = TagFactory.create(name="special")
        speciality_tag = TagFactory.create(name="speciality")

        test_posts[4].tags.add(special_tag, speciality_tag)

        posts = PostSearch("-mir* speci*").get_posts()
        assert test_posts[0] not in posts
        assert test_posts[1] not in posts
        assert test_posts[2] not in posts
        assert test_posts[3] not in posts
        assert test_posts[4] in posts


@pytest.mark.django_db
class TestTagID:
    def test_id_equal(self):
        post = PostFactory.create()
        tag = TagFactory.create()
        post.tags.add(tag)
        ps = PostSearch(f"tag_id={tag.pk}")
        posts = ps.get_posts()
        assert len(posts) == 1
        assert posts[0].pk == post.pk


@pytest.mark.django_db
class TestTagAliases:
    def test_include_only_tag_alias(self):
        """Ensure that PostSearch only returns posts that have a tag linked to a
        tag alias"""
        common_tag = TagFactory.create()

        included_posts = PostFactory.create_batch(10)
        included_tag = TagFactory.create()
        included_tag_alias = TagAliasFactory.create(tag=included_tag)
        for post in included_posts:
            post.tags.add(included_tag)
            post.tags.add(common_tag)

        not_included_posts = PostFactory.create_batch(10)
        not_included_tag = TagFactory.create()
        for post in not_included_posts:
            post.tags.add(not_included_tag)
            post.tags.add(common_tag)

        ps = PostSearch(f"alias={included_tag_alias.name}")
        posts = ps.get_posts()
        assert len(posts.difference(Post.posts.filter(tags__in=[included_tag]))) == 0
        assert len(
            posts.difference(Post.posts.filter(tags__in=[not_included_tag]))
        ) == len(not_included_posts)

    def test_include_tag_alias_with_wildcard(self):
        """Ensure that PostSearch only returns posts matching an alias with a wildcard
        tag alias"""
        common_tag = TagFactory.create(name="common")

        included_posts = PostFactory.create_batch(10)
        included_tag = TagFactory.create()
        _included_tag_alias = TagAliasFactory.create(name="blunder", tag=included_tag)
        for post in included_posts:
            post.tags.add(included_tag)
            post.tags.add(common_tag)

        not_included_posts = PostFactory.create_batch(10)
        not_included_tag = TagFactory.create(name="success")
        for post in not_included_posts:
            post.tags.add(not_included_tag)
            post.tags.add(common_tag)

        ps = PostSearch("alias=blu*er")
        posts = ps.get_posts()
        assert len(posts.difference(Post.posts.filter(tags__in=[included_tag]))) == 0
        assert len(
            posts.difference(Post.posts.filter(tags__in=[not_included_tag]))
        ) == len(not_included_posts)

    def test_exclude_tag_alias_with_wildcard(self):
        """Ensure tag filter negation works with tag aliases using wildcards"""
        common_tag = TagFactory.create(name="common")

        included_posts = PostFactory.create_batch(10)
        included_tag = TagFactory.create()
        _included_tag_alias = TagAliasFactory.create(name="blunder", tag=included_tag)
        for post in included_posts:
            post.tags.add(included_tag)
            post.tags.add(common_tag)

        not_included_posts = PostFactory.create_batch(10)
        not_included_tag = TagFactory.create(name="success")
        for post in not_included_posts:
            post.tags.add(not_included_tag)
            post.tags.add(common_tag)

        ps = PostSearch("-alias=blu*er")
        posts = ps.get_posts()
        assert len(posts.difference(Post.posts.filter(tags__in=[included_tag]))) == len(
            not_included_posts
        )
        assert (
            len(posts.difference(Post.posts.filter(tags__in=[not_included_tag]))) == 0
        )


@pytest.mark.django_db
class TestPostID:
    def test_id_equal(self):
        post = PostFactory.create()
        ps = PostSearch(f"id={post.pk}")
        posts = ps.get_posts()
        assert len(posts) == 1
        assert posts[0].pk == post.pk

    def test_id_less_than(self):
        post1 = PostFactory.create(id=1)
        post2 = PostFactory.create(id=2)
        post3 = PostFactory.create(id=3)
        post4 = PostFactory.create(id=4)
        post5 = PostFactory.create(id=5)
        ps = PostSearch(f"id<{post3.pk}")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))
        assert post_ids == {post1.pk, post2.pk}
        assert post4.pk not in post_ids
        assert post5.pk not in post_ids

    def test_id_greater_than(self):
        post1 = PostFactory.create(id=1)
        post2 = PostFactory.create(id=2)
        post3 = PostFactory.create(id=3)
        post4 = PostFactory.create(id=4)
        post5 = PostFactory.create(id=5)
        ps = PostSearch(f"id>{post3.pk}")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))
        assert post_ids == {post4.pk, post5.pk}
        assert post1.pk not in post_ids
        assert post2.pk not in post_ids

    def test_negative_arg(self):
        post = PostFactory.create()
        with pytest.raises(ValidationError):
            PostSearch(f"id=-{post.pk}")


@pytest.mark.django_db
class TestCommentCount:
    def test_comment_count_equal(self):
        post1 = PostFactory.create()
        post2 = PostFactory.create()
        post3 = PostFactory.create()

        comment_count = 10
        CommentFactory.create_batch(comment_count, post=post3)

        ps = PostSearch(f"comment_count={comment_count}")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post1.pk not in post_ids
        assert post2.pk not in post_ids
        assert post3.pk in post_ids

    def test_comment_count_less_than(self):
        post1 = PostFactory.create()
        post2 = PostFactory.create()
        post3 = PostFactory.create()
        CommentFactory.create_batch(5, post=post2)
        CommentFactory.create_batch(10, post=post3)

        ps = PostSearch("comment_count<10")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post1.pk in post_ids
        assert post2.pk in post_ids
        assert post3.pk not in post_ids

    def test_comment_count_greater_than(self):
        post1 = PostFactory.create()
        post2 = PostFactory.create()
        post3 = PostFactory.create()
        CommentFactory.create_batch(1, post=post1)
        CommentFactory.create_batch(5, post=post2)
        CommentFactory.create_batch(10, post=post3)

        ps = PostSearch("comment_count>1")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post1.pk not in post_ids
        assert post2.pk in post_ids
        assert post3.pk in post_ids

    def test_negative_arg(self):
        PostFactory.create()
        with pytest.raises(ValidationError):
            PostSearch("comment_count>-5")


@pytest.mark.django_db
class TestCommentedBy:
    def test_commented_by_user(self):
        post1 = PostFactory.create()
        post2 = PostFactory.create()
        post3 = PostFactory.create()
        commenter = UserFactory.create()
        other = UserFactory.create()
        CommentFactory.create(post=post1, user=commenter)
        CommentFactory.create(post=post2, user=commenter)
        CommentFactory.create(post=post3, user=other)

        ps = PostSearch(f"comment_by={commenter.username}")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post1.pk in post_ids
        assert post2.pk in post_ids
        assert post3.pk not in post_ids

    def test_commented_by_user_with_wildcard(self):
        post1 = PostFactory.create()
        post2 = PostFactory.create()
        post3 = PostFactory.create()
        commenter1 = UserFactory.create(username="tom123")
        commenter2 = UserFactory.create(username="tommy")
        commenter3 = UserFactory.create(username="angela")
        CommentFactory.create(post=post1, user=commenter1)
        CommentFactory.create(post=post2, user=commenter2)
        CommentFactory.create(post=post3, user=commenter3)

        ps = PostSearch("comment_by=tom*")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post1.pk in post_ids
        assert post2.pk in post_ids
        assert post3.pk not in post_ids


@pytest.mark.django_db
class TestFavoritedCount:
    def test_favorited_equal(self):
        post1, post2, post3, post4 = PostFactory.create_batch(4)

        FavoriteFactory.create_batch(5, post=post2)
        FavoriteFactory.create_batch(10, post=post3)
        FavoriteFactory.create_batch(50, post=post4)

        ps = PostSearch("favorite_count=10")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post1.pk not in post_ids
        assert post2.pk not in post_ids
        assert post3.pk in post_ids
        assert post4.pk not in post_ids

    def test_favorited_greater_than(self):
        post1, post2, post3, post4, post5 = PostFactory.create_batch(5)

        FavoriteFactory.create_batch(5, post=post2)
        FavoriteFactory.create_batch(10, post=post3)
        FavoriteFactory.create_batch(50, post=post4)
        FavoriteFactory.create_batch(100, post=post5)

        ps = PostSearch("favorite_count>10")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post1.pk not in post_ids
        assert post2.pk not in post_ids
        assert post3.pk not in post_ids
        assert post4.pk in post_ids
        assert post5.pk in post_ids

    def test_favorited_less_than(self):
        post1, post2, post3, post4, post5 = PostFactory.create_batch(5)

        FavoriteFactory.create_batch(5, post=post2)
        FavoriteFactory.create_batch(10, post=post3)
        FavoriteFactory.create_batch(50, post=post4)
        FavoriteFactory.create_batch(100, post=post5)

        ps = PostSearch("favorite_count<11")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post1.pk in post_ids
        assert post2.pk in post_ids
        assert post3.pk in post_ids
        assert post4.pk not in post_ids
        assert post5.pk not in post_ids


@pytest.mark.django_db
class TestTagCount:
    def test_tag_count_equal(self):
        post0, post1, post2, post3 = PostFactory.create_batch(4)

        tags = TagFactory.create_batch(30)

        post1.tags.set(tags[:5])
        post2.tags.set(tags[5:15])
        post3.tags.set(tags[15:])

        ps = PostSearch("tag_count=10")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post0.pk not in post_ids
        assert post1.pk not in post_ids
        assert post2.pk in post_ids
        assert post3.pk not in post_ids

    def test_tag_count_greater_than(self):
        post0, post1, post2, post3 = PostFactory.create_batch(4)

        tags = TagFactory.create_batch(30)

        post1.tags.set(tags[:5])
        post2.tags.set(tags[5:15])
        post3.tags.set(tags[15:])

        ps = PostSearch("tag_count>5")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post0.pk not in post_ids
        assert post1.pk not in post_ids
        assert post2.pk in post_ids
        assert post3.pk in post_ids

    def test_tag_count_less_than(self):
        post0, post1, post2, post3 = PostFactory.create_batch(4)

        tags = TagFactory.create_batch(30)

        post1.tags.set(tags[:5])
        post2.tags.set(tags[5:15])
        post3.tags.set(tags[15:])

        ps = PostSearch("tag_count<10")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post0.pk in post_ids
        assert post1.pk in post_ids
        assert post2.pk not in post_ids
        assert post3.pk not in post_ids


@pytest.mark.django_db
class TestFiletype:
    def test_filetype_extension(self):
        gif_posts = PostFactory.create_batch(3, type=SupportedMediaType.GIF.name)
        png_posts = PostFactory.create_batch(4, type=SupportedMediaType.PNG.name)

        ps = PostSearch("file_extension=gif")
        matching_posts = ps.get_posts()

        found_post_ids = set(matching_posts.values_list("pk", flat=True))
        gif_post_ids = {p.pk for p in gif_posts}
        png_post_ids = {p.pk for p in png_posts}
        assert all(pid in found_post_ids for pid in gif_post_ids)
        assert not any(pid in found_post_ids for pid in png_post_ids)


@pytest.mark.django_db
class TestMimetype:
    def test_supported_mimetype(self):
        gif_posts = PostFactory.create_batch(3, type=SupportedMediaType.GIF.name)
        png_posts = PostFactory.create_batch(4, type=SupportedMediaType.PNG.name)

        ps = PostSearch("mimetype=image/gif")
        found_posts = ps.get_posts()

        found_post_ids = set(found_posts.values_list("pk", flat=True))
        gif_post_ids = {p.pk for p in gif_posts}
        png_post_ids = {p.pk for p in png_posts}
        assert all(pid in found_post_ids for pid in gif_post_ids)
        assert not any(pid in found_post_ids for pid in png_post_ids)

    def test_invalid_mimetype(self):
        """Invalid mimetypes should raise a validation error"""
        _posts = PostFactory.create_batch(3, type=SupportedMediaType.GIF.name)
        with pytest.raises(ValidationError):
            PostSearch("mimetype=not_a/mimetype")

    def test_valid_but_unsupported_mimetype(self):
        """Unsupported mimetypes should raise a validation error"""
        _posts = PostFactory.create_batch(3, type=SupportedMediaType.GIF.name)
        with pytest.raises(ValidationError):
            PostSearch("mimetype=text/html")


@pytest.mark.django_db
class TestHeight:
    def test_image_height_equal(self):
        post0, post1, post2, post3 = PostFactory.create_batch(4)

        ImageFactory(post=post0, height=1000)
        ImageFactory(post=post1, height=2000)
        ImageFactory(post=post2, height=3000)
        ImageFactory(post=post3, height=4000)

        ps = PostSearch("height=1000")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post0.pk in post_ids
        assert post1.pk not in post_ids
        assert post2.pk not in post_ids
        assert post3.pk not in post_ids

    def test_image_height_greater_than(self):
        post0, post1, post2, post3 = PostFactory.create_batch(4)

        ImageFactory(post=post0, height=1000)
        ImageFactory(post=post1, height=2000)
        ImageFactory(post=post2, height=3000)
        ImageFactory(post=post3, height=4000)

        ps = PostSearch("height>2000")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post0.pk not in post_ids
        assert post1.pk not in post_ids
        assert post2.pk in post_ids
        assert post3.pk in post_ids

    def test_image_height_less_than(self):
        post0, post1, post2, post3 = PostFactory.create_batch(4)

        ImageFactory(post=post0, height=1000)
        ImageFactory(post=post1, height=2000)
        ImageFactory(post=post2, height=3000)
        ImageFactory(post=post3, height=4000)

        ps = PostSearch("height<3000")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post0.pk in post_ids
        assert post1.pk in post_ids
        assert post2.pk not in post_ids
        assert post3.pk not in post_ids


@pytest.mark.django_db
class TestWidth:
    def test_image_width_equal(self):
        post0, post1, post2, post3 = PostFactory.create_batch(4)

        ImageFactory(post=post0, width=1000)
        ImageFactory(post=post1, width=2000)
        ImageFactory(post=post2, width=3000)
        ImageFactory(post=post3, width=4000)

        ps = PostSearch("width=1000")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post0.pk in post_ids
        assert post1.pk not in post_ids
        assert post2.pk not in post_ids
        assert post3.pk not in post_ids

    def test_image_width_greater_than(self):
        post0, post1, post2, post3 = PostFactory.create_batch(4)

        ImageFactory(post=post0, width=1000)
        ImageFactory(post=post1, width=2000)
        ImageFactory(post=post2, width=3000)
        ImageFactory(post=post3, width=4000)

        ps = PostSearch("width>2000")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post0.pk not in post_ids
        assert post1.pk not in post_ids
        assert post2.pk in post_ids
        assert post3.pk in post_ids

    def test_image_width_less_than(self):
        post0, post1, post2, post3 = PostFactory.create_batch(4)

        ImageFactory(post=post0, width=1000)
        ImageFactory(post=post1, width=2000)
        ImageFactory(post=post2, width=3000)
        ImageFactory(post=post3, width=4000)

        ps = PostSearch("width<3000")
        posts = ps.get_posts()

        post_ids = set(posts.values_list("pk", flat=True))
        assert post0.pk in post_ids
        assert post1.pk in post_ids
        assert post2.pk not in post_ids
        assert post3.pk not in post_ids


@pytest.mark.django_db
class TestRatingLabel:
    @pytest.mark.parametrize("rating_level", list(RatingLevel))
    def test_rating_valid_rating_labels(self, rating_level):
        PostFactory.create_batch(10, rating_level=RatingLevel.SAFE)
        PostFactory.create_batch(10, rating_level=RatingLevel.UNRATED)
        PostFactory.create_batch(10, rating_level=RatingLevel.QUESTIONABLE)
        PostFactory.create_batch(10, rating_level=RatingLevel.EXPLICIT)

        ps = PostSearch(f"rating_label={rating_level.name.lower()}")
        posts = ps.get_posts()

        assert not posts.difference(Post.posts.filter(rating_level=rating_level.value))

    def test_rating_bad_label(self):
        with pytest.raises(ValidationError):
            PostSearch("rating_label=not_a_label")


@pytest.mark.django_db
class TestRatingNumber:
    @pytest.mark.parametrize("rating_level", [r.value for r in RatingLevel])
    def test_rating_num_equal(self, rating_level):
        PostFactory.create_batch(10, rating_level=RatingLevel.SAFE)
        PostFactory.create_batch(10, rating_level=RatingLevel.UNRATED)
        PostFactory.create_batch(10, rating_level=RatingLevel.QUESTIONABLE)
        PostFactory.create_batch(10, rating_level=RatingLevel.EXPLICIT)

        ps = PostSearch(f"rating_num={rating_level}")
        posts = ps.get_posts()

        assert not posts.difference(Post.posts.filter(rating_level=rating_level))

    @pytest.mark.parametrize("rating_level", [r.value for r in RatingLevel])
    def test_rating_num_greater_than(self, rating_level):
        PostFactory.create_batch(10, rating_level=RatingLevel.SAFE)
        PostFactory.create_batch(10, rating_level=RatingLevel.UNRATED)
        PostFactory.create_batch(10, rating_level=RatingLevel.QUESTIONABLE)
        PostFactory.create_batch(10, rating_level=RatingLevel.EXPLICIT)

        ps = PostSearch(f"rating_num>{rating_level}")
        posts = ps.get_posts()

        assert not posts.difference(Post.posts.filter(rating_level__gt=rating_level))

    @pytest.mark.parametrize("rating_level", [r.value for r in RatingLevel])
    def test_rating_num_less_than(self, rating_level):
        PostFactory.create_batch(10, rating_level=RatingLevel.SAFE)
        PostFactory.create_batch(10, rating_level=RatingLevel.UNRATED)
        PostFactory.create_batch(10, rating_level=RatingLevel.QUESTIONABLE)
        PostFactory.create_batch(10, rating_level=RatingLevel.EXPLICIT)

        ps = PostSearch(f"rating_num<{rating_level}")
        posts = ps.get_posts()

        assert not posts.difference(Post.posts.filter(rating_level__lt=rating_level))


@pytest.mark.django_db
class TestSource:
    def test_src_url_exact(self):
        post1 = PostFactory.create(src_url="https://test1.example.com")
        post2 = PostFactory.create(src_url="https://test2.example.com")
        post3 = PostFactory.create(src_url="https://test3.example.com")

        ps = PostSearch("source=https://test1.example.com")
        posts = ps.get_posts()

        assert post1 in posts
        assert post2 not in posts
        assert post3 not in posts

    def test_src_url_with_wildcard(self):
        post1 = PostFactory.create(src_url="https://test1.example.com")
        post2 = PostFactory.create(src_url="https://test2.example.com")
        post3 = PostFactory.create(src_url="https://test3.example.com")
        post4 = PostFactory.create(src_url="https://test.example.org")

        ps = PostSearch("source=https://test*.example.com")
        posts = ps.get_posts()

        assert post1 in posts
        assert post2 in posts
        assert post3 in posts
        assert post4 not in posts

    def test_src_url_with_start_and_end_wildcard(self):
        post1 = PostFactory.create(src_url="https://test1.example.com")
        post2 = PostFactory.create(src_url="https://test2.example.com")
        post3 = PostFactory.create(src_url="https://test3.example.com")

        post4 = PostFactory.create(src_url="https://test1.example.org")

        ps = PostSearch("source=*test1.example.*")
        posts = ps.get_posts()

        assert post1 in posts
        assert post2 not in posts
        assert post3 not in posts
        assert post4 in posts

    def test_src_url_with_multipart_wildcard(self):
        post1 = PostFactory.create(src_url="http://test.exam.com")
        post2 = PostFactory.create(src_url="http://test.example.wow")
        post3 = PostFactory.create(src_url="https://test.examine.com")
        post4 = PostFactory.create(src_url="https://test.mine.org")

        ps = PostSearch("source=http*test.exam*e.*")
        posts = ps.get_posts()

        assert post1 not in posts
        assert post2 in posts
        assert post3 in posts
        assert post4 not in posts


@pytest.mark.django_db
class TestPostedBy:
    def test_uploaded_by_exact(self):
        post0, post1, post2, post3 = PostFactory.create_batch(4)

        ps = PostSearch(f"uploaded_by={post0.uploader.username}")
        posts = ps.get_posts()

        assert post0 in posts
        assert post1 not in posts
        assert post2 not in posts
        assert post3 not in posts

    def test_uploaded_by_with_wildcard(self):
        user1 = UserFactory.create(username="user1")
        user2 = UserFactory.create(username="user2")
        nobody = UserFactory.create(username="nobody")
        u1_posts = PostFactory.create_batch(4, uploader=user1)
        u2_posts = PostFactory.create_batch(4, uploader=user2)
        nb_posts = PostFactory.create_batch(4, uploader=nobody)

        ps = PostSearch("uploaded_by=user*")
        posts = ps.get_posts()

        for post in u1_posts + u2_posts:
            assert post in posts

        for post in nb_posts:
            assert post not in posts

    def test_uploaded_by_with_multi_part_wildcard(self):
        user1 = UserFactory.create(username="i_am_user1")
        user2 = UserFactory.create(username="i_am_user2")
        nobody = UserFactory.create(username="i_am_nobody")
        somebody = UserFactory.create(username="i_am_user_somebody")

        u1_post = PostFactory.create(uploader=user1)
        u2_post = PostFactory.create(uploader=user2)
        nb_post = PostFactory.create(uploader=nobody)
        sb_post = PostFactory.create(uploader=somebody)

        ps = PostSearch("uploaded_by=*am*body")
        posts = ps.get_posts()

        assert u1_post not in posts
        assert u2_post not in posts
        assert nb_post in posts
        assert sb_post in posts


@pytest.mark.django_db
class TestPostedOn:
    def test_exact_date(self):
        """Confirm search by date only (YYYY-MM-DD) returns correct posts"""
        date1 = datetime.datetime(2020, 2, 22, tzinfo=timezone.get_default_timezone())
        post1 = PostFactory.create(post_date=date1)

        date2 = datetime.datetime(2022, 2, 22, tzinfo=timezone.get_default_timezone())
        post2 = PostFactory.create(post_date=date2)

        date3 = datetime.datetime(2024, 2, 22, tzinfo=timezone.get_default_timezone())
        post3 = PostFactory.create(post_date=date3)

        ps = PostSearch(f"posted_on={date1.strftime('%Y-%m-%d')}")
        found_posts = ps.get_posts()

        assert post1 in found_posts
        assert post2 not in found_posts
        assert post3 not in found_posts

    def test_exact_iso(self):
        """Confirm search by exact ISO date returns correct posts"""
        date1 = datetime.datetime(2020, 2, 22, tzinfo=timezone.get_default_timezone())
        post1 = PostFactory.create(post_date=date1)

        date2 = datetime.datetime(2022, 2, 22, tzinfo=timezone.get_default_timezone())
        post2 = PostFactory.create(post_date=date2)

        date3 = datetime.datetime(2024, 2, 22, tzinfo=timezone.get_default_timezone())
        post3 = PostFactory.create(post_date=date3)

        ps = PostSearch(f"posted_on={date1.isoformat()}")
        found_posts = ps.get_posts()

        assert post1 in found_posts
        assert post2 not in found_posts
        assert post3 not in found_posts

    def test_before_date(self):
        """Confirm search by date before (YYYY-MM-DD) returns correct posts"""
        date1 = datetime.datetime(2020, 2, 22, tzinfo=timezone.get_default_timezone())
        post1 = PostFactory.create(post_date=date1)

        date2 = datetime.datetime(2022, 2, 22, tzinfo=timezone.get_default_timezone())
        post2 = PostFactory.create(post_date=date2)

        date3 = datetime.datetime(2024, 2, 22, tzinfo=timezone.get_default_timezone())
        post3 = PostFactory.create(post_date=date3)

        ps = PostSearch(f"posted_on<{date2.strftime('%Y-%m-%d')}")
        found_posts = ps.get_posts()

        assert post1 in found_posts
        assert post2 not in found_posts
        assert post3 not in found_posts

    def test_before_iso(self):
        """Confirm search by before ISO date returns correct posts"""
        date1 = datetime.datetime(2020, 2, 22, tzinfo=timezone.get_default_timezone())
        post1 = PostFactory.create(post_date=date1)

        date2 = datetime.datetime(2022, 2, 22, tzinfo=timezone.get_default_timezone())
        post2 = PostFactory.create(post_date=date2)

        date3 = datetime.datetime(2024, 2, 22, tzinfo=timezone.get_default_timezone())
        post3 = PostFactory.create(post_date=date3)

        ps = PostSearch(f"posted_on<{date2.isoformat()}")
        found_posts = ps.get_posts()

        assert post1 in found_posts
        assert post2 not in found_posts
        assert post3 not in found_posts

    def test_after_date(self):
        """Confirm search by date after (YYYY-MM-DD) returns correct posts"""
        date1 = datetime.datetime(2020, 2, 22, tzinfo=timezone.get_default_timezone())
        post1 = PostFactory.create(post_date=date1)

        date2 = datetime.datetime(2022, 2, 22, tzinfo=timezone.get_default_timezone())
        post2 = PostFactory.create(post_date=date2)

        date3 = datetime.datetime(2024, 2, 22, tzinfo=timezone.get_default_timezone())
        post3 = PostFactory.create(post_date=date3)

        ps = PostSearch(f"posted_on>{date2.strftime('%Y-%m-%d')}")
        found_posts = ps.get_posts()

        assert post1 not in found_posts
        assert post2 not in found_posts
        assert post3 in found_posts

    def test_after_iso(self):
        """Confirm search by before ISO date returns correct posts"""
        date1 = datetime.datetime(2020, 2, 22, tzinfo=timezone.get_default_timezone())
        post1 = PostFactory.create(post_date=date1)

        date2 = datetime.datetime(2022, 2, 22, tzinfo=timezone.get_default_timezone())
        post2 = PostFactory.create(post_date=date2)

        date3 = datetime.datetime(2024, 2, 22, tzinfo=timezone.get_default_timezone())
        post3 = PostFactory.create(post_date=date3)

        ps = PostSearch(f"posted_on>{date2.isoformat()}")
        found_posts = ps.get_posts()

        assert post1 not in found_posts
        assert post2 not in found_posts
        assert post3 in found_posts

    def test_invalid_date_format(self):
        """an invalid date argument should raise a validation error"""
        with pytest.raises(ValidationError):
            PostSearch("posted_on=2020:01:02")


@pytest.mark.django_db
class TestCollection:
    def test_collection_yes(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        c1, c2 = CollectionFactory.create_batch(2)
        c1.posts.set([p1])
        c2.posts.set([p2])

        ps = PostSearch("collection=yes")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk in post_ids
        assert p2.pk in post_ids
        assert p3.pk not in post_ids

    def test_collection_no(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        c1, c2 = CollectionFactory.create_batch(2)
        c1.posts.set([p1])
        c2.posts.set([p2])

        ps = PostSearch("collection=no")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk not in post_ids
        assert p2.pk not in post_ids
        assert p3.pk in post_ids

    def test_invalid_choice(self):
        with pytest.raises(ValidationError):
            PostSearch("collection=yeehaw")


@pytest.mark.django_db
class TestCollectionID:
    def test_exact_id(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        c1, c2, c3 = CollectionFactory.create_batch(3)
        c1.posts.set([p1])
        c2.posts.set([p2])
        c3.posts.set([p3])

        ps = PostSearch(f"collection_id={c1.pk}")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk in post_ids
        assert p2.pk not in post_ids
        assert p3.pk not in post_ids

    def test_id_less_than(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        c1 = CollectionFactory.create(pk=1)
        c2 = CollectionFactory.create(pk=2)
        c3 = CollectionFactory.create(pk=3)
        c1.posts.set([p1])
        c2.posts.set([p2])
        c3.posts.set([p3])

        ps = PostSearch(f"collection_id<{c3.pk}")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk in post_ids
        assert p2.pk in post_ids
        assert p3.pk not in post_ids

    def test_id_greater_than(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        c1 = CollectionFactory.create(pk=1)
        c2 = CollectionFactory.create(pk=2)
        c3 = CollectionFactory.create(pk=3)
        c1.posts.set([p1])
        c2.posts.set([p2])
        c3.posts.set([p3])

        ps = PostSearch(f"collection_id>{c1.pk}")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk not in post_ids
        assert p2.pk in post_ids
        assert p3.pk in post_ids

    def test_exact_id_multiple(self):
        # Search returns posts in _both_ collections when using multiple
        # collection_id tokens
        p1, p2, p3 = PostFactory.create_batch(3)
        c1, c2, c3, c4 = CollectionFactory.create_batch(4)
        c1.posts.set([p1])
        c2.posts.set([p2])
        c3.posts.set([p3])
        c4.posts.set([p1, p2])

        ps = PostSearch(f"collection_id={c4.pk}")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))
        assert p1.pk in post_ids
        assert p2.pk in post_ids
        assert p3.pk not in post_ids


@pytest.mark.django_db
class TestCollectionName:
    def test_name_simple(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        c1, c2 = CollectionFactory.create_batch(2)
        c1.posts.set([p1])
        c2.posts.set([p2])

        ps = PostSearch(f'collection_name="{c1.name}"')
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk in post_ids
        assert p2.pk not in post_ids
        assert p3.pk not in post_ids

    def test_name_with_wildcard(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        c1 = CollectionFactory.create(name="my_collection1")
        c2 = CollectionFactory.create(name="my_collection2")
        c3 = CollectionFactory.create(name="secret_collection")
        c1.posts.set([p1])
        c2.posts.set([p2])
        c3.posts.set([p3])

        ps = PostSearch("collection_name=my*")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk in post_ids
        assert p2.pk in post_ids
        assert p3.pk not in post_ids

    def test_name_with_wildcard_and_surrounding_quotes(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        c1 = CollectionFactory.create(name="my_collection1")
        c2 = CollectionFactory.create(name="my_collection2")
        c3 = CollectionFactory.create(name="secret_collection")
        c1.posts.set([p1])
        c2.posts.set([p2])
        c3.posts.set([p3])

        ps = PostSearch('collection_name="my*"')
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk in post_ids
        assert p2.pk in post_ids
        assert p3.pk not in post_ids


@pytest.mark.django_db
class TestParent:
    def test_has_parent(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        p2.parent = p1
        p2.save()

        ps = PostSearch("parent=yes")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk not in post_ids
        assert p2.pk in post_ids
        assert p3.pk not in post_ids

    def test_has_no_parent(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        p2.parent = p1
        p2.save()

        ps = PostSearch("parent=no")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk in post_ids
        assert p2.pk not in post_ids
        assert p3.pk in post_ids

    def test_parent_id_exact(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        p2.parent = p1
        p2.save()
        p3.parent = p2
        p3.save()

        ps = PostSearch(f"parent_id={p1.pk}")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk not in post_ids
        assert p2.pk in post_ids
        assert p3.pk not in post_ids


@pytest.mark.django_db
class TestChildren:
    def test_has_children(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        p2.parent = p1
        p2.save()
        p3.parent = p2
        p3.save()

        ps = PostSearch("child=yes")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk in post_ids
        assert p2.pk in post_ids
        assert p3.pk not in post_ids

    def test_has_no_children(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        p2.parent = p1
        p2.save()
        p3.parent = p2
        p3.save()

        ps = PostSearch("child=no")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk not in post_ids
        assert p2.pk not in post_ids
        assert p3.pk in post_ids

    def test_children_id_exact(self):
        p1, p2, p3 = PostFactory.create_batch(3)
        p2.parent = p1
        p2.save()
        p3.parent = p2
        p3.save()

        ps = PostSearch(f"child_id={p2.pk}")
        posts = ps.get_posts()
        post_ids = set(posts.values_list("pk", flat=True))

        assert p1.pk in post_ids
        assert p2.pk not in post_ids
        assert p3.pk not in post_ids


class TestComplexQueries:
    """Tests for complex queries using multiple token types"""
