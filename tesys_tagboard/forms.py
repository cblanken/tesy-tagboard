from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, URLValidator
from django.utils.translation import gettext_lazy as _

from .enums import RatingLevel
from .models import Collection, Tag, TagAlias, TagCategory
from .validators import validate_rating_level, validate_tagset, validate_tagset_name


def tagset_to_array(value) -> set[int] | None:
    if value is None:
        return None
    try:
        return {int(x) for x in value}
    except ValueError as e:
        msg = "A tagset may only contain integers"
        raise ValidationError(msg) from e


class TagsetField(forms.Field):
    default_validators = [validate_tagset]
    """A Field representing a set of Tag IDs"""

    def to_python(self, value) -> set[int] | None:
        return tagset_to_array(value)


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = [
            Tag.name.field.name,
            Tag.category.field.name,
            Tag.rating_level.field.name,
        ]

    def clean_rating_level(self):
        if not self.cleaned_data.get("rating_level"):
            return self.fields["rating_level"].initial
        return self.cleaned_data["rating_level"]


class TagAliasForm(forms.ModelForm):
    class Meta:
        model = TagAlias
        fields = [TagAlias.name.field.name, TagAlias.tag.field.name]


class TagCategoryForm(forms.ModelForm):
    class Meta:
        model = TagCategory
        fields = [
            TagCategory.name.field.name,
            TagCategory.parent.field.name,
            TagCategory.light_bg.field.name,
            TagCategory.light_fg.field.name,
            TagCategory.dark_bg.field.name,
            TagCategory.dark_fg.field.name,
        ]


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = [
            Collection.name.field.name,
            Collection.desc.field.name,
            Collection.public.field.name,
        ]


class UploadMedia(forms.Form):
    src_url = forms.URLField(label=_("Source"), required=False, assume_scheme="https")
    title = forms.CharField(
        max_length=1000, required=False, validators=[MaxLengthValidator(1000)]
    )
    file = forms.FileField(label=_("File"), required=True)
    rating_level = forms.ChoiceField(
        choices=RatingLevel.choices,
        initial=RatingLevel.UNRATED,
        required=False,
        validators=[validate_rating_level],
    )
    tagset = TagsetField(required=False, widget=forms.HiddenInput)


class PostSearchForm(forms.Form):
    """Form for searching Posts
    tagset: an array of tag IDs
    funcset: an array of search function IDs
    """

    tagset = TagsetField(required=False, widget=forms.HiddenInput)
    funcset = TagsetField(required=False, widget=forms.HiddenInput)


class TagsetForm(forms.Form):
    size = forms.CharField(required=False)
    tagset = TagsetField(required=False, widget=forms.HiddenInput)
    tagset_name = forms.CharField(required=True, validators=[validate_tagset_name])


class PostForm(forms.Form):
    """Form for Posts
    src_url = a URL linking to the source of the media
    file = a file object representing the Media
    tags: an array of tag IDs"""

    title = forms.CharField(max_length=200, label=_("Title"), required=False)
    src_url = forms.URLField(
        label=_("Source"),
        required=False,
        assume_scheme="https",
        max_length=1024,
        validators=[URLValidator(["https", "http", "ftp"])],
    )
    rating_level = forms.ChoiceField(choices=RatingLevel.choices, required=False)
    tagset = TagsetField(required=False, widget=forms.HiddenInput)


class AddCommentForm(forms.Form):
    """Form for adding Comments"""

    text = forms.CharField(
        widget=forms.Textarea,
        required=True,
        max_length=2048,
        validators=[MaxLengthValidator(2048)],
    )


class EditCommentForm(forms.Form):
    """Form for editing Comments"""

    comment_id = forms.IntegerField(required=True)
    text = forms.CharField(
        widget=forms.Textarea,
        required=True,
        max_length=2048,
        validators=[MaxLengthValidator(2048)],
    )


class EditUserSettingsForm(forms.Form):
    """Form for editing User settings"""

    filter_tags = TagsetField(required=False, widget=forms.HiddenInput)
    blur_tags = TagsetField(required=False, widget=forms.HiddenInput)
    blur_rating_level = forms.ChoiceField(choices=RatingLevel.choices)
