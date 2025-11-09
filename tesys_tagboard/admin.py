from django.contrib import admin

from .models import Artist
from .models import Audio
from .models import Comment
from .models import Favorite
from .models import Image
from .models import Media
from .models import MediaType
from .models import Pool
from .models import Post
from .models import Tag
from .models import TagCategory
from .models import Video


@admin.register(TagCategory)
class TagCategoryAdmin(admin.ModelAdmin):
    list_display = ["pk", "category", "prefix"]
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
    list_display = ["pk", "name", "category"]
    search_fields = ["name", "category__name"]
    list_filter = ["category"]


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ["user", "tag", "bio"]
    search_fields = ["user__name", "tag__name"]
    autocomplete_fields = ["user", "tag"]
    ordering = ["user"]


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ["orig_name", "type", "src_url", "upload_date", "edit_date"]
    search_fields = ["orig_name"]
    autocomplete_fields = ["type"]


@admin.register(MediaType)
class MediaTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "template", "desc"]
    search_fields = ["name", "template"]


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = [
        "file",
        "meta__id",
        "meta__orig_name",
        "meta__type",
        "md5",
        "phash",
        "dhash",
    ]
    autocomplete_fields = ["meta"]
    search_fields = ["meta__type", "og_name", "source"]


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    autocomplete_fields = ["meta"]
    search_fields = ["meta__type", "og_name", "source"]


@admin.register(Audio)
class AudioAdmin(admin.ModelAdmin):
    autocomplete_fields = ["meta"]
    search_fields = ["meta__type", "og_name", "source"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["user", "text"]
    list_filter = ["user"]
    autocomplete_fields = ["user"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = [
        "uploader",
        "post_date",
        "media__orig_name",
        "media__src_url",
    ]
    search_fields = ["media__orig_name, source__url"]
    autocomplete_fields = ["media"]


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    autocomplete_fields = ["user", "posts"]
    search_fields = ["user", "name", "desc"]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    autocomplete_fields = ["user", "post"]
    search_fields = ["user"]
