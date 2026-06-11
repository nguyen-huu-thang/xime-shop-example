from __future__ import annotations

from pydantic import BaseModel, Field


class CartCreateRequest(BaseModel):
    product_option_id: int = Field(gt=0, alias="productOptionId")
    quantity: int = Field(default=1, ge=1)

    model_config = {"populate_by_name": True}


class CartUpdateRequest(BaseModel):
    quantity: int = Field(ge=1)
