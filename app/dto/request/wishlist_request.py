from pydantic import BaseModel, Field


class WishlistCreateRequest(BaseModel):
    productId: int = Field(gt=0)
