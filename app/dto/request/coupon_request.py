from __future__ import annotations

from pydantic import BaseModel, Field


class CouponCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    discount: float = Field(ge=0)
    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")
    is_active: bool = Field(default=True, alias="isActive")

    model_config = {"populate_by_name": True}


class CouponUpdateRequest(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    discount: float | None = Field(default=None, ge=0)
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")
    is_active: bool | None = Field(default=None, alias="isActive")

    model_config = {"populate_by_name": True}
