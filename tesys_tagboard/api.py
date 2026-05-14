from ninja import NinjaAPI, Schema
from ninja.orm import create_schema

from .models import Tag, TagCategory

api = NinjaAPI()

TagSchema = create_schema(Tag)


class TagIn(Schema):
    name: str
    category_name: str | None = None
    rating_level: int


@api.get("/up")
def hello(request):
    return "This tagboard is up and running :)"


@api.get("/tags", response=list[TagSchema])
def get_tags(request):
    return Tag.tags.all()


@api.post("/tags")
def create_tag(request, params: TagIn):
    """
    Create a tag. Please provide:
    - **tag name**
    - **tag category** name
    - and **tag rating level** (defaults to 0)
    """

    if params.category_name is None:
        category = None
    else:
        category = TagCategory.objects.get(name=params.category_name.lower())
        if category is None:
            return {"error": "That tag category doesn't exist"}

    tag = Tag.tags.create(
        name=params.name,
        category=category,
        rating_level=params.rating_level,
    )
    return {"id": tag.pk}
