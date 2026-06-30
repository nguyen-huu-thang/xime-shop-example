from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CouponCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    discount: float = Field(ge=0)
    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")
    is_active: bool = Field(default=True, alias="isActive")
    # ── Nâng cấp coupon ──────────────────────────────────────────────────────────
    discount_type: Literal["fixed", "percent"] = Field(default="fixed", alias="discountType")
    max_discount: float | None = Field(default=None, ge=0, alias="maxDiscount")
    min_order_amount: float = Field(default=0, ge=0, alias="minOrderAmount")
    applies_to: Literal["product", "shipping"] = Field(default="product", alias="appliesTo")
    usage_limit: int | None = Field(default=None, ge=1, alias="usageLimit")
    per_user_once: bool = Field(default=False, alias="perUserOnce")

    model_config = {"populate_by_name": True}


class CouponUpdateRequest(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    discount: float | None = Field(default=None, ge=0)
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")
    is_active: bool | None = Field(default=None, alias="isActive")
    discount_type: Literal["fixed", "percent"] | None = Field(default=None, alias="discountType")
    max_discount: float | None = Field(default=None, ge=0, alias="maxDiscount")
    min_order_amount: float | None = Field(default=None, ge=0, alias="minOrderAmount")
    applies_to: Literal["product", "shipping"] | None = Field(default=None, alias="appliesTo")
    usage_limit: int | None = Field(default=None, ge=1, alias="usageLimit")
    per_user_once: bool | None = Field(default=None, alias="perUserOnce")

    model_config = {"populate_by_name": True}
