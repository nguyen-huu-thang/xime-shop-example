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
