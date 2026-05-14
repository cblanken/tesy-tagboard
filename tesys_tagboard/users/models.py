from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from tesys_tagboard.enums import RatingLevel
from tesys_tagboard.models import Tag


class User(AbstractUser):
    """
    Default custom user model for Tesy's Tagboard.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.

    Attributes:
        name: A user's "username"
        first_name: A user's real first name
        last_name: A user's real last name
        blur_tags: A set of tags to automatically blur posts by
        filter_tags: A set of tags to automatically filter posts by
        blur_level: An integer matching one of the options for a Post's rating_level
    """

    # First and last name do not cover name patterns around the globe
    name = models.CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    filter_tags = models.ManyToManyField(
        Tag, related_name="filter_tags_users", blank=True
    )
    blur_tags = models.ManyToManyField(Tag, related_name="blur_tags_users", blank=True)
    blur_rating_level = models.PositiveSmallIntegerField(
        default=RatingLevel.EXPLICIT,
        choices=RatingLevel.choices,
        db_comment="An integer matching one of the options for a Post's rating_level",
    )

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"username": self.username})

    def with_permissions(self, perms: list[Permission]) -> User:
        self.user_permissions.add(*perms)
        self.save()
        return self

    def add_to_group(self, group_name: str) -> User:
        """Add a user to the group specified by `group_name`"""
        group = Group.objects.get(name=group_name)
        self.groups.add(group)
        return self
