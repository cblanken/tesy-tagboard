from django.contrib import admin

from .models import (
    Artist,
    Audio,
    Collection,
    Comment,
    DefaultPostTag,
    Favorite,
    Image,
    Post,
    PostTagHistory,
    SourceHistory,
    Tag,
    TagAlias,
    TagCategory,
    Video,
)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["pk", "name", "category", "rating_level"]
    search_fields = ["name", "category__name"]
    list_filter = ["category__name"]


@admin.register(DefaultPostTag)
class DefaultPostTagAdmin(admin.ModelAdmin):
    list_display = ["tag"]
    search_fields = ["tag__name", "tag__category__name"]


@admin.register(TagAlias)
class TagAliasAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "name",
        "tag__name",
        "tag__category",
        "tag__rating_level",
    ]
    search_fields = ["name", "tag__name", "tag__category"]
    list_filter = ["tag__category", "tag__rating_level"]


@admin.register(TagCategory)
class TagCategoryAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "name",
        "parent",
        "light_bg",
        "light_fg",
        "dark_bg",
        "dark_fg",
    ]
    search_fields = ["name", "pk"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if form:
            form.base_fields["light_bg"].required = False
            form.base_fields["light_fg"].required = False
            form.base_fields["dark_bg"].required = False
            form.base_fields["dark_fg"].required = False
        return form


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ["user", "tag", "bio"]
    search_fields = ["user__name", "tag__name"]
    autocomplete_fields = ["user", "tag"]
    ordering = ["user"]


@admin.register(SourceHistory)
class SourceHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "user",
        "src_url",
        "mod_time",
    ]
    search_fields = ["user", "src_url"]
    list_filter = ["user"]


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "post__id",
        "file",
        "md5",
        "phash",
        "dhash",
    ]
    autocomplete_fields = ["post"]
    list_filter = ["post__type"]
    search_fields = ["pk", "post__id", "orig_name", "md5", "phash", "dhash"]


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "post__id",
        "file",
        "md5",
    ]
    autocomplete_fields = ["post"]
    list_filter = ["post__type"]
    search_fields = ["pk", "post__id", "orig_name", "md5"]


@admin.register(Audio)
class AudioAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "post__id",
        "file",
        "md5",
    ]
    autocomplete_fields = ["post"]
    list_filter = ["post__type"]
    search_fields = ["pk", "post__id", "orig_name", "md5"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["pk", "user", "post_id", "post_date", "edit_date", "text"]
    list_filter = ["user"]
    search_fields = ["text", "user__username", "post__title", "post_date", "edit_date"]
    autocomplete_fields = ["user"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "uploader",
        "post_date",
        "rating_level",
        "src_url",
    ]
    search_fields = ["pk", "src_url", "uploader__username"]
    autocomplete_fields = ["uploader"]
    list_filter = ["rating_level", "uploader"]


@admin.register(PostTagHistory)
class PostTagHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "user",
        "tags",
        "mod_time",
    ]
    search_fields = ["user", "tags"]
    list_filter = ["user"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "user",
        "name",
        "desc",
        "public",
    ]
    autocomplete_fields = ["user", "posts"]
    search_fields = ["user__username", "name", "desc"]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "user",
        "post",
    ]
    autocomplete_fields = ["user", "post"]
    search_fields = ["user"]
