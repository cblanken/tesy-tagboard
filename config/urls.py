from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path
from django.views import defaults as default_views

from tesys_tagboard import views
from tesys_tagboard.api import api

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("posts/", views.posts, name="posts"),
    path(
        "posts/autocomplete/", views.post_search_autocomplete, name="post-autocomplete"
    ),
    path("posts/<int:media_id>/", views.post, name="post"),
    path("tags/", views.tags, name="tags"),
    path("tags/autocomplete/", views.tag_search_autocomplete, name="tag-autocomplete"),
    path("upload/", views.upload, name="upload"),
    path("help/", views.search_help, name="help"),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("tesys_tagboard.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
    # Django components
    path("", include("django_components.urls")),
]
if settings.DEBUG:
    # Static file serving when using Gunicorn + Uvicorn for local web socket development
    urlpatterns += staticfiles_urlpatterns()

# API URLS
urlpatterns += [path("api/", api.urls)]

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
        path("__reload__/", include("django_browser_reload.urls")),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]
