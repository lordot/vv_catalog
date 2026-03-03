from pydantic import BaseModel, ConfigDict


class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str = None
    type_id: int | None = None
    subtype_id: int | None = None
    image: str | None = None
    link: str | None = None
    count: int | None = None
