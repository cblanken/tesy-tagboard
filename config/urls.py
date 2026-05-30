from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, re_path
from django.views import defaults as default_views
from django.views.static import serve

from tesys_tagboard import views
from tesys_tagboard.api import api

admin_url = (
    f"{settings.ADMIN_URL}/" if settings.ADMIN_URL[-1] != "/" else settings.ADMIN_URL
)

post_urls = [
    path("", views.posts, name="posts"),
    path("autocomplete/", views.post_search_autocomplete, name="autocomplete"),
    path("<int:post_id>/", views.post, name="post"),
    path("<int:post_id>/add-comment/", views.add_comment, name="add-post-comment"),
    path("<int:post_id>/delete/", views.delete_post, name="delete-post"),
    path("<int:post_id>/edit/", views.edit_post, name="edit-post"),
    path(
        "<int:post_id>/comments/toggle_lock/",
        views.toggle_comment_lock,
        name="toggle-post-comment-lock",
    ),
    path("comments/edit/", views.edit_comment, name="edit-post-comment"),
    path("comments/delete/", views.delete_comment, name="delete-post-comment"),
]

tag_urls = [
    # Endpoints for individual tags
    # Tag endpoints
    path("create/", views.create_tag, name="create-tag"),
    path("delete/<int:tag_id>/", views.delete_tag, name="delete-tag"),
    path("update/<int:tag_id>/", views.update_tag, name="update-tag"),
    path("restore/<int:tag_id>/", views.restore_tag, name="restore-tag"),
]

tag_alias_urls = [
    # Tag alias endpoints
    path("create/", views.create_tag_alias, name="create-tag-alias"),
    path("delete/<int:tag_alias_id>/", views.delete_tag_alias, name="delete-tag-alias"),
    path("update/<int:tag_alias_id>/", views.update_tag_alias, name="update-tag-alias"),
]

tag_category_urls = [
    # Tag category endpoints
    path("create/", views.create_tag_category, name="create-tag-category"),
    path(
        "update/<int:tag_category_id>",
        views.update_tag_category,
        name="update-tag-category",
    ),
    path(
        "delete/<int:tag_category_id>",
        views.delete_tag_category,
        name="delete-tag-category",
    ),
]

tags_urls = [
    # Endpoints related to tag operations
    path("", views.tags, name="tags"),
    path("autocomplete/", views.tag_search_autocomplete, name="tag-autocomplete"),
    path("confirm/", views.confirm_tagset, name="confirm-tagset"),
    path("tag/", include(tag_urls)),
    path("alias/", include(tag_alias_urls)),
    path("category/", include(tag_category_urls)),
]

favorite_urls = [
    path("add/<int:post_id>", views.add_favorite, name="add-favorite"),
    path("remove/<int:post_id>", views.remove_favorite, name="remove-favorite"),
]

collection_urls = [
    path("", views.collections, name="collections"),
    path("<int:collection_id>/", views.collection, name="collection"),
    path(
        "<int:collection_id>/update/", views.update_collection, name="update-collection"
    ),
    path(
        "<int:collection_id>/delete/", views.delete_collection, name="delete-collection"
    ),
    path("create/", views.create_collection, name="create-collection"),
    path(
        "<int:collection_id>/add/",
        views.add_post_to_collection,
        name="collection-add-post",
    ),
    path(
        "<int:collection_id>/remove/",
        views.remove_post_from_collection,
        name="collection-remove-post",
    ),
]

urlpatterns = [
    path("", views.home, name="home"),
    path("posts/", include(post_urls)),
    path("tags/", include(tags_urls)),
    path("favorites/", include(favorite_urls)),
    path("collections/", include(collection_urls)),
    path("upload/", views.upload, name="upload"),
    path("help/", views.search_help, name="help"),
    # Set theme
    path("toggle-theme/", views.toggle_theme, name="toggle-theme"),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("tesys_tagboard.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
    # Django components
    path("", include("django_components.urls")),
    # API URLS
    path("api/", api.urls),
]

if settings.DEBUG:
    # Static file serving when using Gunicorn + Uvicorn for local web socket development
    urlpatterns += staticfiles_urlpatterns()

    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns = [
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
        *urlpatterns,
    ]

if "debug_toolbar" in settings.INSTALLED_APPS and settings.DEBUG_TOOLBAR:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
        *urlpatterns,
    ]

if "silk" in settings.INSTALLED_APPS and settings.SILKY_PYTHON_PROFILER:
    urlpatterns = [
        path("silk/", include("silk.urls", namespace="silk")),
        *urlpatterns,
    ]

if not settings.PRODUCTION:
    urlpatterns = [
        path("__reload__/", include("django_browser_reload.urls")),
        *urlpatterns,
    ]

# Serve media files locally when not in PRODUCTION mode and DEBUG is disabled
if not settings.PRODUCTION and not settings.DEBUG:
    urlpatterns = [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {
                "document_root": settings.MEDIA_ROOT,
            },
        ),
        *urlpatterns,
    ]
