from dataclasses import dataclass
from http import HTTPStatus
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any

import markdown
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import permission_required
from django.contrib.messages.storage.base import Message
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import F, OrderBy, Q
from django.db.utils import DatabaseError, IntegrityError
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
)
from django.http.response import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import gettext as _

from .components.add_tagset.add_tagset import AddTagsetComponent
from .components.comment.comment import CommentComponent
from .components.favorite_toggle.favorite_toggle import FavoriteToggleComponent
from .decorators import require
from .enums import MediaCategory, RatingLevel, SupportedMediaType
from .forms import (
    AddCommentForm,
    CollectionForm,
    EditCommentForm,
    PostForm,
    TagAliasForm,
    TagCategoryForm,
    TagForm,
    TagsetForm,
    tagset_to_array,
)
from .models import (
    Audio,
    Collection,
    Comment,
    DefaultPostTag,
    Favorite,
    Image,
    Post,
    Tag,
    TagAlias,
    TagCategory,
    Video,
    csv_to_tag_ids,
)
from .search import (
    PostSearch,
    PostSearchTokenCategory,
    SearchTokenFilterNotImplementedError,
    autocomplete_tag_aliases,
    autocomplete_tags,
)
from .validators import (
    validate_media_file_type_matches_ext,
    validate_supported_media_file,
    validate_tagset,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser
    from django.core.files.uploadedfile import UploadedFile
    from django.db.models import QuerySet
    from django_htmx.middleware import HtmxDetails


class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


class HttpUnprocessableContent(HttpResponse):
    status_code = 422


User = get_user_model()


@dataclass
class Link:
    text: str
    href: str


@require(["GET"], login=False)
def home(request: HttpRequest) -> TemplateResponse:
    links = [Link(link[0], link[1]) for link in settings.HOMEPAGE_LINKS]

    try:
        markdown_path = Path("tesys_tagboard/home.md")
        with Path.open(markdown_path, encoding="utf-8") as fp:
            markdown_content = fp.read()
    except OSError:
        markdown_content = "The `home.md` file could not be found!"

    md = markdown.Markdown(extensions=["sane_lists"])
    context = {
        "links": links,
        "markdown_html": SafeString(md.convert(markdown_content)),
        "post_count": Post.posts.count(),
    }
    return TemplateResponse(request, "pages/home.html", context)


@require(["GET"], login=False)
def post(request: HtmxHttpRequest, post_id: int) -> TemplateResponse | HttpResponse:
    # GET request
    all_posts = Post.posts.order_by("post_date").values("pk", "post_date")
    previous_post = None
    next_post = None
    for i, post in enumerate(all_posts):
        if post.get("pk") == post_id:
            previous_post = all_posts[i - 1] if i > 0 else None
            next_post = all_posts[i + 1] if i < len(all_posts) - 1 else None

    posts = Post.posts
    if request.user.is_authenticated:
        favorites = Favorite.favorites.for_user(request.user.pk)
        posts = posts.annotate_favorites(favorites)

    posts = posts.filter(pk=post_id).select_related("uploader")

    post = get_object_or_404(posts.prefetch_related("posttaghistory_set"))
    comments = post.comment_set.order_by("-post_date").select_related("user")

    comments_pager = Paginator(comments, 10, 5)
    comments_page_num = request.GET.get("page", 1)
    comments_page = comments_pager.get_page(comments_page_num)
    tags = Tag.tags.for_post(post)

    post_tag_snapshots = post.posttaghistory_set.order_by("mod_time")
    post_tag_history_tag_ids = [
        csv_to_tag_ids(tags_snapshot.tags) if tags_snapshot.tags.strip() != "" else []
        for tags_snapshot in post_tag_snapshots
    ]
    tag_history_unique_ids = set(chain(*post_tag_history_tag_ids))

    # Collect tag_history tags in a single DB call
    history_tags_by_id = {
        tag.pk: tag
        for tag in Tag.tags.select_related("category").filter(
            pk__in=tag_history_unique_ids
        )
    }

    tag_history = [
        [history_tags_by_id.get(int(tag_id)) for tag_id in tag_ids]
        for tag_ids in post_tag_history_tag_ids
    ]

    tag_history = post.posttaghistory_set.order_by("-mod_time")
    for tag_snapshot in tag_history:
        tag_snapshot.tag_objects = [
            history_tags_by_id.get(int(tag_id))
            for tag_id in csv_to_tag_ids(tag_snapshot.tags)
        ]

    source_history = post.sourcehistory_set.order_by("-mod_time")

    context = {
        "post": post,
        "previous_post": previous_post,
        "next_post": next_post,
        "rating_levels": list(RatingLevel),
        "tags": tags,
        "meta_tag_names": " ".join(tag.name for tag in tags),
        "comments_pager": comments_pager,
        "comments_page": comments_page,
        "collections": Collection.objects.for_user(request.user.pk),
        "tag_history": tag_history,
        "source_history": source_history,
        "child_posts": Post.posts.with_gallery_data(request.user).filter(parent=post),
    }

    return TemplateResponse(request, "pages/post.html", context)


@require(["POST"], login=True)
@permission_required(["tesys_tagboard.change_post"], raise_exception=True)
def edit_post(
    request: HtmxHttpRequest, post_id: int
) -> TemplateResponse | HttpResponse:
    user: User | AnonymousUser = request.user
    post = get_object_or_404(Post.posts.filter(pk=post_id))
    if not (user.is_authenticated or user.has_perm("edit", post)):
        return HttpResponseForbidden(
            f'The user "{user.get_username()}" is not allowed to edit this post'
        )

    data: dict[str, str | list[Any] | None] = {
        key: request.POST.get(key) for key in request.POST
    }
    data["tagset"] = request.POST.getlist("tagset")

    form = PostForm(data)
    if not form.is_valid():
        return HttpUnprocessableContent("Invalid form data")

    if title := form.cleaned_data.get("title"):
        post.title = title

    if src_url := form.cleaned_data.get("src_url"):
        post.save_with_src_history(request.user, src_url)

    if rating_level := form.cleaned_data.get("rating_level"):
        post.rating_level = rating_level

    if tagset := form.cleaned_data.get("tagset"):
        tags = Tag.tags.in_tagset(tagset)
        post.save_with_tag_history(request.user, tags)

    post.save()
    return redirect(reverse("post", args=[post.pk]))


@require(["DELETE"])
@permission_required(["tesys_tagboard.delete_post"], raise_exception=True)
def delete_post(
    request: HtmxHttpRequest, post_id: int
) -> TemplateResponse | HttpResponse:
    try:
        post = Post.posts.get(pk=post_id)
        post.delete()
        msg = f"The post with ID {post_id} has been successfully deleted"
        messages.add_message(request, messages.INFO, msg)
        return redirect(reverse("posts"))

    except Post.DoesNotExist:
        return HttpResponseNotFound("That post doesn't exist")


@require(["POST"], login=False)
def confirm_tagset(request: HtmxHttpRequest):
    if request.htmx:
        form = TagsetForm(request.POST)
        if form.is_valid():
            size = form.cleaned_data.get("size")
            tagset_name = form.cleaned_data.get("tagset_name")
            tagset = tagset_to_array(request.POST.getlist(tagset_name, None))

            # Confirm tagset for target tagset_name exists and is valid
            try:
                validate_tagset(tagset)
                if tagset:
                    tags = Tag.tags.in_tagset(tagset)
                    kwargs = {
                        "size": size,
                        "tags": tags,
                        "tagset_name": tagset_name,
                        "add_tag_enabled": True,
                    }
                    return AddTagsetComponent.render_to_response(
                        request=request, kwargs=kwargs
                    )
            except ValidationError:
                return HttpResponseBadRequest("Invalid tags provided")

    return HttpResponseBadRequest("Invalid request")


@require(["POST"])
@permission_required(
    ["tesys_tagboard.change_post", "tesys_tagboard.lock_comments"], raise_exception=True
)
def toggle_comment_lock(
    request: HtmxHttpRequest, post_id: int
) -> TemplateResponse | HttpResponse:
    try:
        post = Post.posts.get(pk=post_id)
        post.locked_comments = not post.locked_comments
        post.save()
        return TemplateResponse(
            request, "pages/post.html#add-comments", context={"post": post}
        )

    except Post.DoesNotExist:
        return HttpResponseNotFound("That post doesn't exist")


@require(["GET", "POST"], login=False)
def posts(request: HtmxHttpRequest) -> TemplateResponse | HttpResponse:
    user: User | AnonymousUser = request.user
    posts = Post.posts.with_gallery_data(user)
    tags: QuerySet[Tag] | None = None

    context = {}
    try:
        if request.GET:
            if q := request.GET.get("q"):
                context |= {"query": q}
                ps = PostSearch(q)
                posts = ps.get_posts().with_gallery_data(request.user)

        elif request.POST:
            ps = PostSearch(request.POST)
            if user.is_authenticated:
                posts = ps.get_posts().with_gallery_data(request.user)
                tagset = request.POST.getlist("tagset")
                tags = Tag.tags.in_tagset(tagset)
            else:
                posts = ps.get_posts()
    except ValidationError as err:
        messages.add_message(request, messages.ERROR, SafeString(err.message))
    except SearchTokenFilterNotImplementedError as err:
        messages.add_message(request, messages.ERROR, SafeString(err.message))

    pager = Paginator(posts, 36, 4)
    page_num = int(request.GET.get("page", 1))
    page = pager.get_page(page_num)

    context |= {
        "pager": pager,
        "page": page,
        "tags": tags,
    }
    return TemplateResponse(request, "pages/posts.html", context)


@require(["GET", "POST"], login=False)
def tags(request: HtmxHttpRequest) -> TemplateResponse | HttpResponse:
    categories = TagCategory.objects.order_by("-parent", "name")
    try:
        query = request.GET.get("q", "").strip()
        uncategorized_tags = Tag.tags.select_related("category").filter(category=None)
        if query != "":
            uncategorized_tags = uncategorized_tags.filter(name__icontains=query)

        select_related_expr = ["category"]
        select_related_expr.extend(
            [
                "category" + "__parent" * x
                for x in range(1, settings.MAX_TAG_CATEGORY_DEPTH)
            ]
        )

        order_by_expr: list[str | F | OrderBy] = [
            F("category" + "__parent" * x + "__name")
            for x in reversed(range(settings.MAX_TAG_CATEGORY_DEPTH))
        ]
        order_by_expr.append("name")

        categorized_tags = (
            Tag.tags.select_related(*select_related_expr)
            .filter(Q(category__name__icontains=query) | Q(name__icontains=query))
            .filter(~Q(category=None))
            .order_by(*order_by_expr)
        )

        tags_by_cat: dict[str, list[Tag]] = {}
        for tag in categorized_tags:
            path = tag.category.get_full_path()
            tags_by_cat.setdefault(path, [])
            tags_by_cat[path].append(tag)

        alias_query = request.GET.get("aliases", "")
        aliases = (
            TagAlias.aliases.filter(name__icontains=alias_query)
            .select_related("tag", "tag__category")
            .order_by(F("tag__category__name").asc(nulls_first=True))
        )
    except ValidationError:
        return HttpResponseBadRequest("Invalid tag name or alias provided")

    context = {
        "uncategorized_tags": uncategorized_tags,
        "tags_by_cat": tags_by_cat,
        "tag_count": Tag.tags.count(),
        "tag_alias_count": TagAlias.aliases.count(),
        "tag_category_count": TagCategory.objects.count(),
        "tag_name": query,
        "aliases": aliases,
        "categories": categories,
    }

    if request.htmx:
        if request.GET.get("q") is not None:
            return TemplateResponse(request, "pages/tags.html#tag-categories", context)
        if request.GET.get("aliases") is not None:
            return TemplateResponse(request, "pages/tags.html#aliases", context)
        return HttpResponseBadRequest("No search queries provided")

    return TemplateResponse(request, "pages/tags.html", context)


@require(["GET", "POST"])
@permission_required(["tesys_tagboard.add_tag"], raise_exception=True)
def create_tag(request: HtmxHttpRequest) -> TemplateResponse | HttpResponse:
    # Translators: title  for "Create Tag" modal form
    title = _("Create Tag")
    # Translators: label for "Create Tag" submit button
    submit_btn_text = _("Create")
    action_url = reverse("create-tag")
    modal_messages = []
    ctx = {
        "title": title,
        "action_url": action_url,
        "submit_btn_text": submit_btn_text,
    }
    if request.method == "GET":
        form = TagForm()

        ctx |= {"body": form}
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "POST":
        form = TagForm(request.POST)
        ctx |= {"body": form}
        if form.is_valid():
            name = form.cleaned_data.get("name")
            try:
                form.save()
            except IntegrityError:
                msg = Message(
                    messages.ERROR,
                    _(
                        'The tag "%s" could not be created. Tags must '
                        "have a unique name and category."
                    )
                    % name,
                )
            except DatabaseError:
                msg = Message(
                    messages.ERROR,
                    _('The tag "%s" could not be created because of a database error.')
                    % name,
                )
            else:
                msg = Message(
                    messages.SUCCESS,
                    _('The tag "%s" was created successfully.') % name,
                )

            modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)
    return HttpResponse(
        "Tag could not be created", status=HTTPStatus.UNPROCESSABLE_CONTENT
    )


@require(["GET", "POST"])
@permission_required(["tesys_tagboard.change_tag"], raise_exception=True)
def update_tag(
    request: HtmxHttpRequest, tag_id: int
) -> TemplateResponse | HttpResponse:
    modal_messages = []
    ctx = {
        # Translators: title  for "Update Tag" modal form
        "title": _("Update Tag"),
        # Translators: label for "Update Tag" submit button
        "submit_btn_text": _("Update"),
        "action_url": reverse("update-tag", args=[tag_id]),
    }
    try:
        tag: Tag = Tag.tags.get(pk=tag_id)
    except Tag.DoesNotExist:
        return HttpResponse("Tag could not be found", status=HTTPStatus.NOT_FOUND)

    if request.method == "GET":
        form = TagForm(instance=tag)
        ctx |= {"body": form}
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "POST":
        form = TagForm(request.POST, instance=tag)
        ctx |= {"body": form}
        if form.is_valid():
            name = form.cleaned_data.get("name")
            try:
                form.save()
            except DatabaseError:
                msg = Message(
                    messages.ERROR,
                    _('The tag "%s" could not be updated because of a database error.')
                    % name,
                )
            else:
                msg = Message(
                    messages.SUCCESS,
                    _('The "%s" tag was updated successfully.') % name,
                )

            modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)

    return HttpResponse("", status=HTTPStatus.METHOD_NOT_ALLOWED)


@require(["GET", "DELETE"])
@permission_required(["tesys_tagboard.delete_tag"], raise_exception=True)
def delete_tag(
    request: HtmxHttpRequest, tag_id: int
) -> TemplateResponse | HttpResponse:
    modal_messages = []
    ctx = {
        "method": "DELETE",
        # Translators: title  for "Delete Tag" modal form
        "title": _("Delete Tag"),
        "action_url": reverse("delete-tag", args=[tag_id]),
        # Translators: label for "Delete Tag" submit button
        "submit_btn_text": _("Delete"),
        "color": "danger",
        # Translators: tag deletion confirmation message
        "body": _(
            "Are you sure you want to delete this tag? This action cannot be undone "
            "except by an administrator."
        ),
    }
    if request.method == "GET":
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "DELETE":
        try:
            tag = Tag.tags.get(pk=tag_id)
            tag.delete()
        except Tag.DoesNotExist:
            msg = Message(messages.ERROR, _("A tag with the given ID does not exist."))
        except DatabaseError:
            msg = Message(
                messages.ERROR,
                _(
                    'The tag with an ID of "%s" could not be deleted because of a '
                    "database error."
                )
                % tag_id,
            )
        else:
            msg = Message(
                messages.SUCCESS,
                _('The tag "%s" was deleted.') % tag.name,
            )

        modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)
    return HttpResponse(
        "Tag could not be created", status=HTTPStatus.METHOD_NOT_ALLOWED
    )


@require(["GET", "POST"])
@permission_required(["tesys_tagboard.add_tagalias"], raise_exception=True)
def create_tag_alias(request: HtmxHttpRequest) -> TemplateResponse | HttpResponse:
    # Translators: title  for "Create Tag Alias" modal form
    title = _("Create Tag Alias")
    # Translators: label for "Create Tag Alias" submit button
    submit_btn_text = _("Create")
    action_url = reverse("create-tag-alias")
    modal_messages = []
    ctx = {
        "title": title,
        "action_url": action_url,
        "submit_btn_text": submit_btn_text,
    }
    if request.method == "GET":
        form = TagAliasForm()
        ctx |= {"body": form}
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "POST":
        form = TagAliasForm(request.POST)
        ctx |= {"body": form}
        if form.is_valid():
            name = form.cleaned_data.get("name")
            try:
                form.save()
            except IntegrityError:
                msg = Message(
                    messages.ERROR,
                    _('The tag alias "%s" already exists.') % name,
                )
            except DatabaseError:
                msg = Message(
                    messages.ERROR,
                    _("The tag alias could not be created because of a database error.")
                    % name,
                )
            else:
                msg = Message(
                    messages.SUCCESS,
                    _('The tag alias "%s" was created successfully.') % name,
                )

            modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)
    return HttpResponse(
        "Tag alias could not be created", status=HTTPStatus.METHOD_NOT_ALLOWED
    )


@require(["GET", "POST"])
@permission_required(["tesys_tagboard.change_tagalias"], raise_exception=True)
def update_tag_alias(
    request: HtmxHttpRequest, tag_alias_id: int
) -> TemplateResponse | HttpResponse:
    modal_messages = []
    ctx = {
        # Translators: title  for "Update Tag Alias" modal form
        "title": _("Update Tag Alias"),
        # Translators: label for "Update Tag Alias" submit button
        "submit_btn_text": _("Update"),
        "action_url": reverse("update-tag-alias", args=[tag_alias_id]),
    }
    try:
        tag_alias: TagAlias = TagAlias.aliases.get(pk=tag_alias_id)
    except TagAlias.DoesNotExist:
        return HttpResponse("Tag alias could not be found", status=HTTPStatus.NOT_FOUND)

    if request.method == "GET":
        form = TagAliasForm(instance=tag_alias)
        ctx |= {"body": form}
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "POST":
        form = TagAliasForm(request.POST, instance=tag_alias)
        ctx |= {"body": form}
        if form.is_valid():
            name = form.cleaned_data.get("name")
            try:
                form.save()
            except DatabaseError:
                msg = Message(
                    messages.ERROR,
                    _(
                        'The tag alias "%s" could not be updated because of a database '
                        "error."
                    )
                    % name,
                )
            else:
                msg = Message(
                    messages.SUCCESS,
                    _('The tag alias "%s" was updated successfully.') % name,
                )

            modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)

    return HttpResponse("", status=HTTPStatus.METHOD_NOT_ALLOWED)


@require(["GET", "DELETE"])
@permission_required(["tesys_tagboard.delete_tagalias"], raise_exception=True)
def delete_tag_alias(
    request: HtmxHttpRequest, tag_alias_id: int
) -> TemplateResponse | HttpResponse:
    modal_messages = []
    ctx = {
        "method": "DELETE",
        # Translators: title  for "Delete Tag Alias" modal form
        "title": _("Delete Tag Alias"),
        "action_url": reverse("delete-tag-alias", args=[tag_alias_id]),
        # Translators: label for "Delete Tag Alias" submit button
        "submit_btn_text": _("Delete"),
        "color": "danger",
        # Translators: tag alias deletion confirmation message
        "body": _(
            "Are you sure you want to delete this tag alias? This action cannot be "
            "undone except by an administrator."
        ),
    }
    if request.method == "GET":
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "DELETE":
        try:
            tag_alias = TagAlias.aliases.get(pk=tag_alias_id)
            tag_alias.delete()
        except TagAlias.DoesNotExist:
            msg = Message(
                messages.ERROR, _("A tag alias with the given ID does not exist.")
            )
        except DatabaseError:
            msg = Message(
                messages.ERROR,
                _(
                    'The tag alias with an ID of "%s" could not be deleted because of '
                    "a database error."
                )
                % tag_alias_id,
            )
        else:
            msg = Message(
                messages.SUCCESS,
                _('The tag alias "%s" was deleted.') % tag_alias.name,
            )

        modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)
    return HttpResponse(
        "Tag could not be created", status=HTTPStatus.METHOD_NOT_ALLOWED
    )


@require(["GET", "POST"])
@permission_required(["tesys_tagboard.add_tagcategory"], raise_exception=True)
def create_tag_category(request: HtmxHttpRequest) -> TemplateResponse | HttpResponse:
    # Translators: title  for "Create Tag Category" modal form
    title = _("Create Tag Category")
    # Translators: label for "Create Tag Category" submit button
    submit_btn_text = _("Create")
    action_url = reverse("create-tag-category")
    modal_messages = []
    ctx = {
        "title": title,
        "action_url": action_url,
        "submit_btn_text": submit_btn_text,
    }
    if request.method == "GET" and request.htmx:
        form = TagCategoryForm()
        ctx |= {"body": form}
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "POST" and request.htmx:
        form = TagCategoryForm(request.POST)
        ctx |= {"body": form}

        if form.is_valid():
            name = form.cleaned_data.get("name")
            try:
                form.save()
            except IntegrityError:
                msg = Message(
                    messages.ERROR,
                    _(
                        'The tag category "%s" could not be created. Tag categories '
                        "must have a unique name and parent category."
                    )
                    % name,
                )
            except DatabaseError:
                msg = Message(
                    messages.ERROR,
                    _(
                        'The tag category "%s" could not be created because of a '
                        "database error."
                    )
                    % name,
                )
            else:
                msg = Message(
                    messages.SUCCESS,
                    _('The tag "%s" was created successfully.') % name,
                )

            modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)
    return HttpResponse(
        "Tag alias could not be created", status=HTTPStatus.UNPROCESSABLE_CONTENT
    )


@require(["GET", "POST"])
@permission_required(["tesys_tagboard.change_tagcategory"], raise_exception=True)
def update_tag_category(
    request: HtmxHttpRequest, tag_category_id: int
) -> TemplateResponse | HttpResponse:
    modal_messages = []
    ctx = {
        # Translators: title  for "Update Tag Category" modal form
        "title": _("Update Tag Category"),
        # Translators: label for "Update Tag Category" submit button
        "submit_btn_text": _("Update"),
        "action_url": reverse("update-tag-category", args=[tag_category_id]),
    }
    try:
        tag_category: TagCategory = TagCategory.objects.get(pk=tag_category_id)
    except TagCategory.DoesNotExist:
        return HttpResponse(
            "Tag category could not be found", status=HTTPStatus.NOT_FOUND
        )

    if request.method == "GET":
        form = TagCategoryForm(instance=tag_category)
        ctx |= {"body": form}
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "POST":
        form = TagCategoryForm(request.POST, instance=tag_category)
        ctx |= {"body": form}
        if form.is_valid():
            name = form.cleaned_data.get("name")
            try:
                form.save()
            except DatabaseError:
                msg = Message(
                    messages.ERROR,
                    _(
                        'The tag category "%s" could not be updated because of a '
                        "database error."
                    )
                    % name,
                )
            else:
                msg = Message(
                    messages.SUCCESS,
                    _('The "%s" tag category was updated successfully.') % name,
                )

            modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)

    return HttpResponse("", status=HTTPStatus.METHOD_NOT_ALLOWED)


@require(["GET", "DELETE"])
@permission_required(["tesys_tagboard.delete_tagcategory"], raise_exception=True)
def delete_tag_category(
    request: HtmxHttpRequest, tag_category_id: int
) -> TemplateResponse | HttpResponse:
    modal_messages = []
    ctx = {
        "method": "DELETE",
        # Translators: title  for "Delete Tag Category" modal form
        "title": _("Delete Tag Category"),
        "action_url": reverse("delete-tag-category", args=[tag_category_id]),
        # Translators: label for "Delete Tag" submit button
        "submit_btn_text": _("Delete"),
        "color": "danger",
        # Translators: tag deletion confirmation message
        "body": _(
            "Are you sure you want to delete this tag category? This action cannot "
            "be undone except by an administrator."
        ),
    }
    if request.method == "GET":
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "DELETE":
        try:
            tag = TagCategory.objects.get(pk=tag_category_id)
            tag.delete()
        except TagCategory.DoesNotExist:
            msg = Message(
                messages.ERROR, _("A tag category with the given ID does not exist.")
            )
        except DatabaseError:
            msg = Message(
                messages.ERROR,
                _(
                    'The tag with an ID of "%s" could not be deleted because of a '
                    "database error."
                )
                % tag_category_id,
            )
        else:
            msg = Message(
                messages.SUCCESS,
                _('The tag "%s" was deleted.') % tag.name,
            )

        modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)
    return HttpResponse("", status=HTTPStatus.METHOD_NOT_ALLOWED)


@require(["GET"], login=False)
def collections(request: HttpRequest) -> TemplateResponse:
    collections = Collection.objects.public().with_gallery_data()
    pager = Paginator(collections, 36, 4)
    page_num = request.GET.get("page", 1)
    page = pager.get_page(page_num)
    context = {
        "user": request.user,
        "collections": collections,
        "pager": pager,
        "page": page,
    }
    return TemplateResponse(request, "pages/collections.html", context)


@require(["GET"], login=False)
def collection(
    request: HtmxHttpRequest, collection_id: int
) -> TemplateResponse | HttpResponse:
    user = request.user
    collection = get_object_or_404(Collection.objects.filter(pk=collection_id))
    if user == collection.user or collection.public is True:
        posts = Post.posts.with_gallery_data(request.user).filter(
            pk__in=collection.posts.values_list("pk", flat=True)
        )
        pager = Paginator(posts, 25, 5)
        page_num = request.GET.get("page", 1)
        page = pager.get_page(page_num)
        context = {
            "user": request.user,
            "collection": collection,
            "pager": pager,
            "page": page,
        }
    else:
        raise PermissionDenied

    return TemplateResponse(request, "pages/collection.html", context)


@require(["POST"])
@permission_required(["tesys_tagboard.add_collection"], raise_exception=True)
def create_collection(request: HtmxHttpRequest) -> TemplateResponse | HttpResponse:
    # Translators: label for "Create Collection" form
    title = _("Create Collection")
    # Translators: label for "Create Collection" submit button
    submit_btn_text = _("Create")
    action_url = reverse("create-collection")
    modal_messages = []
    ctx = {
        "title": title,
        "action_url": action_url,
        "submit_btn_text": submit_btn_text,
    }
    if request.method == "GET":
        form = CollectionForm()
        ctx |= {"body": form}
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "POST":
        collection = Collection(user=request.user)
        form = CollectionForm(request.POST, instance=collection)
        ctx |= {"body": form}
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                msg = Message(
                    messages.ERROR,
                    _(
                        'The collection "%s" could not be created. Collections must '
                        "have a unique name and description."
                    )
                    % collection.name,
                )
            except DatabaseError:
                msg = Message(
                    messages.ERROR,
                    _(
                        'The collection "%s" could not be created because of a '
                        "database error."
                    )
                    % collection.name,
                )
            else:
                msg = Message(
                    messages.SUCCESS,
                    _('The collection "%s" was created successfully.')
                    % collection.name,
                )
            modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)
    return HttpResponse("", status=HTTPStatus.METHOD_NOT_ALLOWED)


@require(["POST"])
@permission_required(["tesys_tagboard.change_collection"], raise_exception=True)
def update_collection(
    request: HtmxHttpRequest, collection_id: int
) -> TemplateResponse | HttpResponse:
    modal_messages = []
    ctx = {
        # Translators: label for "Update Collection" form
        "title": _("Update Collection"),
        # Translators: label for "Update Collection" submit button
        "action_url": reverse("update-collection", args=[collection_id]),
        "submit_btn_text": _("Update"),
    }
    try:
        collection: Collection = Collection.objects.get(
            user=request.user, pk=collection_id
        )
    except Collection.DoesNotExist:
        return HttpResponse(
            "Collection could not be found", status=HTTPStatus.NOT_FOUND
        )
    if request.method == "GET":
        form = CollectionForm(instance=collection)
        ctx |= {"body": form}
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "POST":
        form = CollectionForm(request.POST, instance=collection)
        ctx |= {"body": form}
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                msg = Message(
                    messages.ERROR,
                    _(
                        'The collection "%s" could not be updated. Collections must '
                        "have a unique name and description."
                    )
                    % collection.name,
                )
            except DatabaseError:
                msg = Message(
                    messages.ERROR,
                    _(
                        'The collection "%s" could not be updated because of a '
                        "database error."
                    )
                    % collection.name,
                )
            else:
                msg = Message(
                    messages.SUCCESS,
                    _('The collection "%s" was updated successfully.')
                    % collection.name,
                )
            modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)
    return HttpResponse("", status=HTTPStatus.METHOD_NOT_ALLOWED)


@require(["GET", "DELETE"])
@permission_required(["tesys_tagboard.delete_collection"], raise_exception=True)
def delete_collection(
    request: HtmxHttpRequest, collection_id: int
) -> TemplateResponse | HttpResponse:
    modal_messages = []
    ctx = {
        "method": "DELETE",
        # Translators: title  for "Delete Collection" modal form
        "title": _("Delete Tag Category"),
        "action_url": reverse("delete-collection", args=[collection_id]),
        # Translators: label for "Delete Collection" submit button
        "submit_btn_text": _("Delete"),
        "color": "danger",
        # Translators: Collection deletion confirmation message
        "body": _("Are you sure you want to delete this collection?"),
    }
    if request.method == "GET":
        return TemplateResponse(request, "modals/form.html", ctx)

    if request.method == "DELETE":
        try:
            collection = Collection.objects.get(user=request.user, pk=collection_id)
            collection.delete()
        except Collection.DoesNotExist:
            msg = Message(
                messages.ERROR,
                _("A collection for the user with the given ID does not exist."),
            )
        except DatabaseError:
            msg = Message(
                messages.ERROR,
                _(
                    'The collection with an ID of "%s" could not be deleted because of '
                    "a database error."
                )
                % collection_id,
            )
        else:
            msg = Message(
                messages.SUCCESS,
                _('The collection "%s" was deleted.') % collection.name,
            )

        modal_messages.append(msg)

        ctx |= {"modal_messages": modal_messages}
        return TemplateResponse(request, "modals/form.html#form-body", ctx)
    return HttpResponse("", status=HTTPStatus.METHOD_NOT_ALLOWED)


@require(["PUT"])
@permission_required(["tesys_tagboard.add_favorite"], raise_exception=True)
def add_favorite(request: HtmxHttpRequest, post_id: int) -> HttpResponse:
    try:
        post = Post.posts.get(pk=post_id)
        favorite = Favorite.favorites.create(post=post, user=request.user)
        favorite.save()

        post.favorited = True
        kwargs = {"post": post}
        return FavoriteToggleComponent.render_to_response(
            request=request, kwargs=kwargs
        )
    except Post.DoesNotExist, Favorite.DoesNotExist:
        return HttpResponse(status=404)
    return HttpResponse("Not allowed", status=403)


@require(["DELETE"])
@permission_required(["tesys_tagboard.delete_favorite"], raise_exception=True)
def remove_favorite(request: HtmxHttpRequest, post_id: int) -> HttpResponse:
    try:
        post = Post.posts.get(pk=post_id)
        Favorite.favorites.get(post=post, user=request.user).delete()

        kwargs = {"post": post}
        return FavoriteToggleComponent.render_to_response(
            request=request, kwargs=kwargs
        )
    except Post.DoesNotExist, Favorite.DoesNotExist:
        return HttpResponse(status=404)
    return HttpResponse("Not allowed", status=403)


@require(["POST"])
@permission_required(["tesys_tagboard.add_post_to_collection"], raise_exception=True)
def add_post_to_collection(
    request: HtmxHttpRequest, collection_id: int
) -> HttpResponse:
    try:
        collection = Collection.objects.get(user=request.user, pk=collection_id)
        post = Post.posts.get(pk=request.POST.get("post"))
        collection.posts.add(post)
        collection.save()

        return render(
            request,
            "collections/picker_item.html",
            context={"collection": collection, "post": post, "checked": True},
            status=200,
        )
    except Post.DoesNotExist, Collection.DoesNotExist:
        return HttpResponse("That post and/or collection doesn't exist", status=404)


@require(["POST"])
@permission_required(
    ["tesys_tagboard.remove_post_from_collection"], raise_exception=True
)
def remove_post_from_collection(
    request: HtmxHttpRequest, collection_id: int
) -> HttpResponse:
    try:
        collection = Collection.objects.get(user=request.user, pk=collection_id)
        post = Post.posts.get(pk=request.POST.get("post"))
        collection.posts.remove(post)
        collection.save()

        return render(
            request,
            "collections/picker_item.html",
            context={"collection": collection, "post": post, "checked": False},
            status=200,
        )
    except Post.DoesNotExist, Collection.DoesNotExist:
        return HttpResponse(status=404)
    return HttpResponse("Not allowed", status=403)


@require(["POST"])
@permission_required(["tesys_tagboard.add_comment"], raise_exception=True)
def add_comment(
    request: HtmxHttpRequest, post_id: int
) -> TemplateResponse | HttpResponse:
    post = get_object_or_404(Post.posts.filter(pk=post_id))
    if post.locked_comments:
        return HttpResponseForbidden("The comments for this post are locked")

    data = AddCommentForm(request.POST)
    if data.is_valid():
        comment = Comment(
            post=post, text=data.cleaned_data.get("text"), user=request.user
        )

        comment.save()
        comments = Comment.objects.for_post(post.pk)
        comments_pager = Paginator(comments, 10, 5)
        comments_page_num = request.GET.get("page", 1)
        comments_page = comments_pager.get_page(comments_page_num)
        context = {
            "post": post,
            "comments": comments,
            "comments_pager": comments_pager,
            "comments_page": comments_page,
        }
        return render(request, "posts/comments.html", context=context)
    return HttpUnprocessableContent()


@require(["POST"])
@permission_required(["tesys_tagboard.change_comment"], raise_exception=True)
def edit_comment(request: HtmxHttpRequest) -> TemplateResponse | HttpResponse:
    data = EditCommentForm(request.POST)
    if data.is_valid():
        comment_id = data.cleaned_data.get("comment_id")
        try:
            comment = Comment.objects.get(pk=comment_id)
            if request.user != comment.user:
                msg = "Only the original poster of a comment may edit it."
                return HttpResponseForbidden(msg)
        except Comment.DoesNotExist:
            msg = "That comment doesn't exist"
            messages.add_message(request, messages.INFO, msg)
            return HttpResponseNotFound(msg)
        else:
            comment.text = data.cleaned_data.get("text")
            comment.save()
            kwargs = {"comment": comment}
            return CommentComponent.render_to_response(request=request, kwargs=kwargs)
    return HttpResponse(status=422)


@require(["DELETE"])
@permission_required(["tesys_tagboard.delete_comment"], raise_exception=True)
def delete_comment(request: HtmxHttpRequest) -> TemplateResponse | HttpResponse:
    comment_id = request.POST.get("comment_id")
    try:
        comment = Comment.objects.get(pk=comment_id)
        if request.user != comment.user:
            msg = "Only the original poster of a comment may edit it."
            return HttpResponseForbidden(msg)
        post = comment.post
        comment.delete()
        comments = Comment.objects.for_post(post.pk)
        context = {"post": post, "comments": comments}
        return render(request, "posts/comments.html", context=context)
    except Comment.DoesNotExist:
        return HttpResponseNotFound("That comment doesn't exist")


@require(["GET"], login=False)
def post_search_autocomplete(
    request: HtmxHttpRequest,
) -> TemplateResponse | HttpResponse:
    if request.method == "GET":
        query = request.GET.get("q", "")
        context = {}
        try:
            ps = PostSearch(query)
        except ValidationError as err:
            context |= {"error": err.message}
        else:
            partial = request.GET.get("partial")
            if request.user.is_authenticated:
                items = ps.autocomplete(partial=partial, user=request.user)
            else:
                items = ps.autocomplete(partial=partial)
            context |= {"items": items}

        return TemplateResponse(request, "posts/search_autocomplete.html", context)

    return HttpResponseNotAllowed(["GET"])


@require(["GET"], login=False)
def tag_search_autocomplete(
    request: HtmxHttpRequest,
) -> TemplateResponse | HttpResponseNotAllowed:
    if request.method == "GET":
        partial = request.GET.get("partial", "")
        if request.user.is_authenticated:
            items = chain(
                autocomplete_tags(
                    Tag.tags.for_user(request.user),
                    partial,
                ),
                autocomplete_tag_aliases(
                    TagAlias.aliases.for_user(request.user),
                    partial,
                ),
            )
        else:
            items = chain(
                autocomplete_tags(Tag.tags.all(), partial),
                autocomplete_tag_aliases(TagAlias.aliases.all(), partial),
            )
        context = {"items": items}
        return TemplateResponse(request, "posts/search_autocomplete.html", context)

    return HttpResponseNotAllowed(["GET"])


def find_duplicate_media_file(media_file):
    media_file_model = None
    match media_file.category():
        case MediaCategory.AUDIO:
            media_file_model = Audio
        case MediaCategory.IMAGE:
            media_file_model = Image
        case MediaCategory.VIDEO:
            media_file_model = Video

    if media_file_model:
        if found_file := media_file_model.objects.filter(md5=media_file.md5).first():
            return found_file
    return None


def handle_media_upload(file: UploadedFile | None, src_url: str | None) -> tuple:
    """Detects media type and creates a new Media derivative"""
    if file is None:
        msg = "The uploaded file cannot be empty"
        raise ValidationError(msg)

    if file.content_type is None:
        msg = "File missing content type"
        raise ValidationError(msg)

    validators = [
        validate_supported_media_file,
        validate_media_file_type_matches_ext,
    ]
    for validator in validators:
        validator(file)

    if smt := SupportedMediaType.select_by_mime(file.content_type):
        media_file = None
        match smt.value.category:
            case MediaCategory.AUDIO:
                media_file = Audio(file=file, mimetype=smt.value.get_mimetype())
            case MediaCategory.IMAGE:
                media_file = Image(file=file, mimetype=smt.value.get_mimetype())
            case MediaCategory.VIDEO:
                media_file = Video(file=file, mimetype=smt.value.get_mimetype())

        duplicate_file = find_duplicate_media_file(media_file)
        return (duplicate_file, media_file)

    msg = "The uploaded file could not be validated"
    raise ValidationError(msg)


@require(["GET", "POST"])
def upload(request: HtmxHttpRequest) -> TemplateResponse | HttpResponse:  # noqa: C901
    context = {
        "rating_levels": list(RatingLevel),
        "default_tags": [
            default.tag
            for default in DefaultPostTag.objects.select_related("tag", "tag__category")
        ],
    }
    user = request.user
    if request.method == "POST":
        if not user.has_perm("tesys_tagboard.add_post"):
            msg = f"You ({user.username}) are not allowed to create posts."
            messages.add_message(request, messages.INFO, msg)
            return HttpResponseForbidden()
        data: dict[str, str | list[Any] | None] = {
            key: request.POST.get(key) for key in request.POST
        }
        data["tagset"] = request.POST.getlist("tagset")
        form = PostForm(data, request.FILES) if request.method == "POST" else PostForm()
        context |= {"form": form}

        # Validate form data
        if not form.is_valid():
            return HttpUnprocessableContent("Invalid form data")

        if tagset := form.cleaned_data.get("tagset"):
            try:
                validate_tagset(tagset)
            except ValidationError:
                return HttpUnprocessableContent("Invalid form data")

        try:
            duplicate, media_file = handle_media_upload(
                form.files.get("file"), form.cleaned_data.get("src_url")
            )

        except ValidationError as err:
            msg = f'Failed to validate uploaded media file because: "{err.message}"'
            messages.add_message(request, messages.INFO, msg)
            return TemplateResponse(request, "pages/upload.html", context=context)
        else:
            if duplicate:
                post_url = reverse("post", args=[duplicate.post.pk])
                msg = mark_safe(  # noqa: S308
                    f"The uploaded file was a duplicate of an existing post which can be found <a href='{post_url}'>here</a>"  # noqa: E501
                )
                messages.add_message(request, messages.WARNING, msg)
                return TemplateResponse(request, "pages/upload.html", context=context)

        try:
            rating_level = int(form.cleaned_data.get("rating_level"))
        except ValueError:
            rating_level = RatingLevel.UNRATED.value
        src_url = form.cleaned_data.get("src_url")
        tags = Tag.tags.in_tagset(tagset)
        if media_type := SupportedMediaType.select_by_mime(
            media_file.file.file.content_type
        ):
            post = Post(
                title=form.cleaned_data.get("title"),
                uploader=request.user,
                rating_level=rating_level,
                src_url=src_url,
                type=media_type.name,
            )
            post.save()
            media_file.post = post
            media_file.save()
            post.save_with_tag_history(post.uploader, tags)
            msg = mark_safe(  # noqa: S308
                f"Your post was created successfully, Check it out <a href='{reverse('post', args=[post.pk])}'>here</a>"  # noqa: E501
            )
            messages.add_message(request, messages.INFO, msg)

        else:
            msg = "The filetype of the uploaded file is not supported."
            messages.add_message(request, messages.ERROR, msg)

    return TemplateResponse(request, "pages/upload.html", context=context)


@require(["GET"], login=False)
def search_help(request: HtmxHttpRequest) -> TemplateResponse:
    context = {"token_categories": list(PostSearchTokenCategory)}
    return TemplateResponse(request, "pages/help.html", context)


@require(["POST"], login=False)
def toggle_theme(request: HtmxHttpRequest) -> HttpResponse:
    theme_checkbox_value = request.POST.get("theme")

    if theme_checkbox_value not in settings.THEMES:
        return HttpResponseBadRequest("Attempt to set theme to an invalid value")

    current_theme = request.session.get("theme")
    other_theme = settings.THEMES[
        (settings.THEMES.index(theme_checkbox_value) + 1) % len(settings.THEMES)
    ]

    if theme_checkbox_value == current_theme:
        request.session["theme"] = other_theme
    else:
        request.session["theme"] = theme_checkbox_value

    return HttpResponse(
        f"Theme changed to {request.session['theme']}",
        status=HTTPStatus.OK,
    )
