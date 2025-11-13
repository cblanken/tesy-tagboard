from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest
from django.http.response import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django_htmx.middleware import HtmxDetails

from .enums import SupportedMediaTypes
from .enums import TagCategory
from .forms import PostForm
from .models import Image
from .models import Media
from .models import Post
from .models import Tag
from .search import PostSearch
from .search import tag_autocomplete


class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


def home(request: HttpRequest) -> TemplateResponse:
    context = {}
    return TemplateResponse(request, "pages/home.html", context)


def about(request: HtmxHttpRequest) -> TemplateResponse:
    context = {}
    return TemplateResponse(request, "pages/about.html", context)


def post(request: HtmxHttpRequest, media_id: int) -> TemplateResponse:
    post = get_object_or_404(Post.objects.filter(media__id=media_id))
    context = {"post": post}
    return TemplateResponse(request, "pages/post.html", context)


def posts(request: HtmxHttpRequest) -> TemplateResponse:
    posts = Post.objects.all()
    context = {"posts": posts}
    return TemplateResponse(request, "pages/posts.html", context)


def tags(request: HtmxHttpRequest) -> TemplateResponse:
    categories = TagCategory.__members__.values()
    tags_by_cat = {
        cat: Tag.objects.filter(category=cat.value.shortcode) for cat in categories
    }

    context = {"tags_by_cat": tags_by_cat}
    return TemplateResponse(request, "pages/tags.html", context)


def post_search_autocomplete(
    request: HtmxHttpRequest,
) -> TemplateResponse | HttpResponseNotAllowed:
    if request.method == "GET":
        tag_prefixes = [key.lower() for key in TagCategory.__members__]
        query = request.GET.get("q", "")
        ps = PostSearch(query, tag_prefixes)
        partial = request.GET.get("partial", "")
        items = ps.autocomplete(partial)

        context = {"items": items}
        return TemplateResponse(request, "posts/search_autocomplete.html", context)

    return HttpResponseNotAllowed(["GET"])


def tag_search_autocomplete(
    request: HtmxHttpRequest,
) -> TemplateResponse | HttpResponseNotAllowed:
    if request.method == "GET":
        partial = request.GET.get("partial", "")
        tags = tag_autocomplete(partial)
        context = {"tags": tags}
        return TemplateResponse(request, "tags/search_autocomplete.html", context)

    return HttpResponseNotAllowed(["GET"])


def handle_media_upload(file: UploadedFile | None, src_url: str | None) -> Media:
    """Detects media type and creates a new Media derivative"""
    if file is None:
        msg = "A file must be provided to upload"
        raise ValueError(msg)

    if file.content_type:
        if smt := SupportedMediaTypes.find(file.content_type):
            media = Media(orig_name=file.name, type=smt.name, src_url=src_url)
            media.save()

            # TODO: match on media type (image, video, audio)...
            img = Image(file=file, meta=media)
            img.save()

            return media

        msg = "That file extension is not supported"
        raise ValueError(msg)

    msg = "Provided file doesn't have a content type"
    raise ValueError(msg)


def upload(request: HtmxHttpRequest) -> TemplateResponse:
    form = (
        PostForm(request.POST, request.FILES)
        if request.method == "POST"
        else PostForm()
    )

    if form.is_valid():
        media = handle_media_upload(
            form.cleaned_data.get("file"), form.cleaned_data.get("src_url")
        )
        post = Post(uploader=request.user, media=media)
        post.save()

    context = {"form": form}
    return TemplateResponse(request, "pages/upload.html", context)


def search_help(request: HtmxHttpRequest) -> TemplateResponse:
    context = {}
    return TemplateResponse(request, "pages/help.html", context)
