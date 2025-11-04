from django.contrib import admin

from .models import Artist
from .models import Comment
from .models import Favorite
from .models import Media
from .models import MediaType
from .models import Pool
from .models import Post
from .models import Tag
from .models import TagCategory


@admin.register(TagCategory)
class TagCategoryAdmin(admin.ModelAdmin):
    list_display = ["category", "prefix"]
    search_fields = ["category", "prefix"]
    list_filter = ["category"]
    ordering = ["prefix"]

    def get_form(self, request, obj=None, *args, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if form:
            form.base_fields[TagCategory.prefix.field.name].required = False
        return form


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "category"]
    search_fields = ["name", "category__name"]
    list_filter = ["category"]


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ["user", "tag", "bio"]
    search_fields = ["user__name", "tag__name"]
    autocomplete_fields = ["user", "tag"]
    ordering = ["user"]


@admin.register(MediaType)
class MediaTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "template", "desc"]
    search_fields = ["name", "template"]


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    autocomplete_fields = ["type"]
    search_fields = ["type", "og_name", "source"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["user", "text"]
    autocomplete_fields = ["user"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    autocomplete_fields = ["media", "tags"]
    search_fields = ["uploader"]


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    autocomplete_fields = ["user", "posts"]
    search_fields = ["user", "name", "desc"]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    autocomplete_fields = ["user", "post"]
    search_fields = ["user"]
