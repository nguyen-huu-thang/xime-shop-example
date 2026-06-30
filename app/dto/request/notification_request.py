from typing import Literal

from pydantic import BaseModel, Field


class NotificationCreateRequest(BaseModel):
    userId: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    message: str | None = Field(default=None)
    type: Literal["push", "email", "sms"] = "push"
    # FE link to navigate to when clicked (e.g. /orders/12)
    # Đường dẫn FE bấm vào điều hướng (vd /orders/12)
    link: str | None = Field(default=None, max_length=255)


class NotificationBroadcastRequest(BaseModel):
    """Admin gửi thông báo tới tất cả user đang hoạt động."""

    title: str = Field(min_length=1, max_length=255)
    message: str | None = Field(default=None)
    link: str | None = Field(default=None, max_length=255)
