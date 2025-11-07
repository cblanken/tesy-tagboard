from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest
from django.template.response import TemplateResponse
from django_htmx.middleware import HtmxDetails

from .forms import UploadImage
from .models import Image
from .models import MediaMetadata
from .models import MediaSource
from .models import MediaType


class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


def home(request: HttpRequest) -> TemplateResponse:
    context = {}
    return TemplateResponse(request, "pages/home.html", context)


def about(request: HtmxHttpRequest) -> TemplateResponse:
    context = {}
    return TemplateResponse(request, "pages/about.html", context)


def posts(request: HtmxHttpRequest) -> TemplateResponse:
    context = {}
    return TemplateResponse(request, "pages/posts.html", context)


def tags(request: HtmxHttpRequest) -> TemplateResponse:
    context = {}
    return TemplateResponse(request, "pages/tags.html", context)


def handle_img_upload(file: UploadedFile | None, src_url: str | None):
    """Detects media type and creates a new MediaSource"""
    if file is None:
        msg = "A file must be provided to upload"
        raise ValueError(msg)
    if file.name:
        try:
            ext = file.name.split(".")[-1]
        except IndexError as e:
            msg = "Uploaded files must have a (dot) extension"
            raise ValueError(msg) from e

    else:
        msg = "Uploaded files must have a name"
        raise ValueError(msg)

    try:
        mediatype = MediaType.objects.get(name__icontains=ext)
    except MediaType.DoesNotExist as e:
        msg = "That file extension is not supported"
        raise ValueError(msg) from e

    if src_url:
        src = MediaSource(url=src_url)
        src.save()
    else:
        src = None

    meta = MediaMetadata(
        orig_name=file,
        type=mediatype,
        source=src,
    )
    meta.save()

    img = Image(
        orig_name=meta.orig_name,
        type=MediaType.objects.get(name__icontains=ext),
        file=file,
    )
    img.save()


def upload(request: HtmxHttpRequest) -> TemplateResponse:
    # TODO: match on media type (image, video, audio)...
    form = (
        UploadImage(request.POST, request.FILES)
        if request.method == "POST"
        else UploadImage()
    )

    if form.is_valid():
        handle_img_upload(
            form.cleaned_data.get("file"), form.cleaned_data.get("src_url")
        )

    context = {"form": form}
    return TemplateResponse(request, "pages/upload.html", context)


def search_help(request: HtmxHttpRequest) -> TemplateResponse:
    context = {}
    return TemplateResponse(request, "pages/help.html", context)
