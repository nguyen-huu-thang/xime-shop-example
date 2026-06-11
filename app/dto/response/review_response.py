from pydantic import BaseModel, ConfigDict


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    user_id: int
    rating: int
    comment: str | None = None
    is_approved: bool
