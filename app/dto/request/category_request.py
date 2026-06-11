from __future__ import annotations

from pydantic import BaseModel, Field


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None)
    parent_id: int | None = Field(default=None, alias="parentId", gt=0)

    model_config = {"populate_by_name": True}


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None)
    parent_id: int | None = Field(default=None, alias="parentId")

    model_config = {"populate_by_name": True}
