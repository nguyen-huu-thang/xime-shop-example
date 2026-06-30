from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    discount: float
    start_date: datetime
    end_date: datetime
    is_active: bool
    discount_type: str
    max_discount: float | None = None
    min_order_amount: float
    applies_to: str
    usage_limit: int | None = None
    used_count: int
    per_user_once: bool
