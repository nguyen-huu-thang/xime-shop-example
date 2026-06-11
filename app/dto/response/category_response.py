from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    parent_id: int | None = None
    hierarchy_path: str | None = None
    hierarchy_path_by_id: str | None = None
