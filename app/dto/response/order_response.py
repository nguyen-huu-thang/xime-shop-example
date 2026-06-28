"""
DTO phản hồi cho đơn hàng.

Thay cấu trúc list-of-lists `[Order, [[id,name,price,qty,url], ...]]` trước đây bằng DTO
Pydantic rõ ràng, nhất quán với phần còn lại của codebase. Giữ nguyên hình dạng JSON
camelCase mà client đang nhận (id, userId, totalAmount, ...).
"""
from __future__ import annotations

from pydantic import BaseModel

from app.entity.order import Order
from app.entity.order_detail import OrderDetail


class OrderDetailResponse(BaseModel):
    id: int
    name: str
    price: float
    quantity: int
    url: str | None = None

    @classmethod
    def from_entity(cls, d: OrderDetail) -> "OrderDetailResponse":
        return cls(
            id=d.id,
            name=d.name,
            price=float(d.price),
            quantity=d.quantity,
            url=d.url,
        )


class OrderResponse(BaseModel):
    id: int
    userId: int
    address: str
    totalAmount: float
    paymentMethod: str
    shippingStatus: str
    paymentStatus: bool
    details: list[OrderDetailResponse]

    @classmethod
    def from_entities(cls, order: Order, details: list[OrderDetail]) -> "OrderResponse":
        return cls(
            id=order.id,
            userId=order.user_id,
            address=order.address,
            totalAmount=float(order.total_amount),
            paymentMethod=order.payment_method,
            shippingStatus=order.shipping_status,
            paymentStatus=order.payment_status,
            details=[OrderDetailResponse.from_entity(d) for d in details],
        )
