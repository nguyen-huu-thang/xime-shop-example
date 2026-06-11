from pydantic import BaseModel, Field


class ReviewCreateRequest(BaseModel):
    userId: int = Field(gt=0)
    productId: int = Field(gt=0)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewUpdateRequest(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
