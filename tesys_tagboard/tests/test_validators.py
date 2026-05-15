import pytest
from django.core.exceptions import ValidationError

from tesys_tagboard.validators import validate_tag_name, validate_tagset


class TestTagSet:
    def test_has_negative_integers(self):
        with pytest.raises(ValidationError):
            validate_tagset([-1, -2, -3])

    def test_has_letters(self):
        with pytest.raises(ValidationError):
            validate_tagset(["a", "b", "c"])

        with pytest.raises(ValidationError):
            validate_tagset([1, 2, 3, "a", "b", "c"])

        with pytest.raises(ValidationError):
            validate_tagset(["a", "b", "c", 1, 2, 3])

        with pytest.raises(ValidationError):
            validate_tagset([1, 2, 3, "a", "b", "c", 1, 2, 3])


class TestTagName:
    def test_name_with_category(self):
        validate_tag_name("category:tag_name")

    def test_name_with_sub_category(self):
        validate_tag_name("category:sub_category:tag_name")

    def test_name_with_spaces(self):
        with pytest.raises(ValidationError):
            validate_tag_name("tag name here")

    def test_name_has_asterisks(self):
        with pytest.raises(ValidationError):
            validate_tag_name("*category*tag*")
