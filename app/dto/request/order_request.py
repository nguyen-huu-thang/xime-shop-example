from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OrderCreateRequest(BaseModel):
    cart: list[int] = Field(min_length=1, alias="cartIds")
    # Địa chỉ giao lấy từ sổ địa chỉ (snapshot vào đơn lúc đặt)
    address_id: int = Field(gt=0, alias="addressId")
    coupon_code: str | None = Field(default=None, max_length=50, alias="couponCode")
    payment_provider: Literal["cod", "mock_online"] = Field(
        default="cod", alias="paymentProvider"
    )

    model_config = {"populate_by_name": True}


class OrderUpdateRequest(BaseModel):
    address: str = Field(min_length=1, max_length=255)


class OrderPreviewRequest(BaseModel):
    cart: list[int] = Field(min_length=1, alias="cartIds")
    address_id: int | None = Field(default=None, gt=0, alias="addressId")
    coupon_code: str | None = Field(default=None, max_length=50, alias="couponCode")

    model_config = {"populate_by_name": True}


class MockPaymentCallbackRequest(BaseModel):
    """Callback giả lập từ trang thanh toán mock."""

    payment_ref: str = Field(min_length=1, max_length=64, alias="paymentRef")
    success: bool = True

    model_config = {"populate_by_name": True}


class ShippingStatusUpdateRequest(BaseModel):
    """Admin cập nhật trạng thái giao hàng của đơn."""

    status: str = Field(min_length=1, max_length=50)
