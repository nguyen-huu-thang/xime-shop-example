from pydantic import BaseModel, Field


class FileUpdateRequest(BaseModel):
    isActive: bool | None = None
    description: str | None = None
    sort: int | None = None
    productId: int | None = Field(default=None, gt=0)
    reviewId: int | None = Field(default=None, gt=0)
