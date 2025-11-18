from django import template

register = template.Library()


@register.filter(name="concat")
def concat(value, arg) -> str:
    """Concatenate string value and arg string."""
    return f"{value}{arg}"
