import pytest
from django.core.exceptions import ValidationError

from tesys_tagboard.validators import tag_name_validator, tagset_validator


class TestTagSet:
    def test_has_negative_integers(self):
        with pytest.raises(ValidationError):
            tagset_validator([-1, -2, -3])

    def test_has_letters(self):
        with pytest.raises(ValidationError):
            tagset_validator(["a", "b", "c"])

        with pytest.raises(ValidationError):
            tagset_validator([1, 2, 3, "a", "b", "c"])

        with pytest.raises(ValidationError):
            tagset_validator(["a", "b", "c", 1, 2, 3])

        with pytest.raises(ValidationError):
            tagset_validator([1, 2, 3, "a", "b", "c", 1, 2, 3])


class TestTagName:
    def test_name_with_category(self):
        tag_name_validator("category:tag_name")

    def test_name_with_sub_category(self):
        tag_name_validator("category:sub_category:tag_name")

    def test_name_with_spaces(self):
        with pytest.raises(ValidationError):
            tag_name_validator("tag name here")

    def test_name_has_asterisks(self):
        with pytest.raises(ValidationError):
            tag_name_validator("*category*tag*")
