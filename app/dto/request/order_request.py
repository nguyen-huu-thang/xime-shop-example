from __future__ import annotations

from pydantic import BaseModel, Field


class OrderCreateRequest(BaseModel):
    cart: list[int] = Field(min_length=1, alias="cartIds")
    address: str = Field(min_length=1, max_length=255)
    payment_method: str = Field(default="", max_length=50, alias="paymentMethod")

    model_config = {"populate_by_name": True}


class OrderUpdateRequest(BaseModel):
    address: str = Field(min_length=1, max_length=255)
