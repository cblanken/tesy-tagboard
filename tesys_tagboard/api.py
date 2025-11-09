from ninja import NinjaAPI
from ninja import Schema
from ninja.orm import create_schema

from .models import Tag
from .models import TagCategory

api = NinjaAPI()

TagSchema = create_schema(Tag)


class TagIn(Schema):
    name: str
    category_shortcode: str | None = None
    rating_level: int


@api.get("/up")
def hello(request):
    return "This tagboard is up and running :)"


@api.get("/tags", response=list[TagSchema])
def get_tags(request):
    return Tag.objects.all()


@api.post("/tags")
def create_tag(request, params: TagIn):
    """
    Create a tag. Please provide:
    - **tag name**
    - **tag category** (2-letter shortcode)
    - and **tag rating level** (defaults to 0)
    """

    if params.category_shortcode is None:
        category = TagCategory.Category.BASIC
    else:
        try:
            category = TagCategory.objects.get(
                category=params.category_shortcode.upper()
            )
        except TagCategory.DoesNotExist:
            return {"error": "That tag category doesn't exist"}

    tag = Tag.objects.create(
        name=params.name, category=category, rating_level=params.rating_level
    )
    return {"id": tag.pk}
