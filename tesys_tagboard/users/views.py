from typing import TYPE_CHECKING

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.paginator import Paginator
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView, UpdateView

from tesys_tagboard.decorators import require
from tesys_tagboard.enums import RatingLevel
from tesys_tagboard.forms import EditUserSettingsForm
from tesys_tagboard.models import Collection, Tag

from .models import User

if TYPE_CHECKING:
    from typing import Any

    from django.db.models import QuerySet
    from django_htmx.middleware import HtmxDetails


class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


@require(["GET", "POST"], login=True)
def user_detail_view(
    request: HtmxHttpRequest, username: str
) -> TemplateResponse | HttpResponse:
    user = get_object_or_404(User, username=username)
    context = {
        "user": user,
        "tab": request.GET.get("tab"),
    }
    if request.user == user and user.is_authenticated:
        # This user's page
        collections = user.collection_set.with_gallery_data()
        favorited_posts = [f.post for f in user.favorite_set.with_gallery_data()]
        for post in favorited_posts:
            post.favorited = True

        favorites_pager = Paginator(favorited_posts, 24, 4)
        fav_page_arg_name = "fav_page"
        favorites_page_num = request.GET.get(fav_page_arg_name, 1)
        favorites_page = favorites_pager.get_page(favorites_page_num)
        context |= {
            "favorites_pager": favorites_pager,
            "favorites_page": favorites_page,
            "favorites_page_arg_name": fav_page_arg_name,
            "collections": collections,
            "blur_rating_levels": list(RatingLevel),
            "filter_tags": user.filter_tags.all(),
            "blur_tags": user.blur_tags.all(),
        }
    else:
        # Other users' pages
        public_collections = Collection.objects.filter(user=user, public=True)
        context |= {
            "collections": public_collections,
        }

    if request.method == "POST":
        if user != request.user:
            return HttpResponseForbidden()

        data: dict[str, str | list[Any] | None] = {
            key: request.POST.get(key) for key in request.POST
        }
        data["filter_tags"] = (
            request.POST.getlist("filter_tags")
            if "filter_tags" in request.POST
            else None
        )
        data["blur_tags"] = (
            request.POST.getlist("blur_tags", None)
            if "blur_tags" in request.POST
            else None
        )

        form = EditUserSettingsForm(data)
        if form.is_valid():
            user.blur_rating_level = form.cleaned_data.get("blur_rating_level")

            if filter_tagset := form.cleaned_data.get("filter_tags"):
                user.filter_tags.set(Tag.tags.in_tagset(filter_tagset))

            if blur_tagset := form.cleaned_data.get("blur_tags"):
                user.blur_tags.set(Tag.tags.in_tagset(blur_tagset))

            user.save()
        else:
            return HttpResponseBadRequest("Invalid form data")

        if request.htmx:
            return TemplateResponse(request, "users/user_detail.html#user-settings")

        return redirect(reverse("users:detail", args=[user.username]), context)

    return TemplateResponse(request, "users/user_detail.html", context)


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None = None) -> User:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self) -> str:
        return reverse("users:detail", kwargs={"username": self.request.user.username})


user_redirect_view = UserRedirectView.as_view()
