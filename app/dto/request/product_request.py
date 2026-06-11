from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    location_address: str = Field(min_length=1, max_length=255, alias="locationAddress")
    description: str | None = None
    category_id: int | None = Field(default=None, alias="categoryId", gt=0)
    discount_percentage: int | None = Field(default=0, alias="discountPercentage", ge=0, le=100)
    price: float | None = Field(default=None, ge=0)
    stock: int = Field(default=0, ge=0)
    attribute: dict[str, list[str]] | None = None

    model_config = {"populate_by_name": True}


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    location_address: str | None = Field(default=None, alias="locationAddress", max_length=255)
    description: str | None = None
    category_id: int | None = Field(default=None, alias="categoryId", gt=0)
    discount_percentage: int | None = Field(default=None, alias="discountPercentage", ge=0, le=100)
    price: float | None = Field(default=None, ge=0)
    stock: int | None = Field(default=None, ge=0)
    attribute: dict[str, list[str]] | None = None

    model_config = {"populate_by_name": True}


class ProductAttributeUpdateRequest(BaseModel):
    """Request body for /products/{id}/attribute endpoint."""
    attribute: list[str]
    value: list[Any]  # list of [[attr_values], [price, stock]]
