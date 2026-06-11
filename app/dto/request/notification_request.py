from typing import Literal

from pydantic import BaseModel, Field


class NotificationCreateRequest(BaseModel):
    userId: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    message: str | None = Field(default=None)
    type: Literal["push", "email", "sms"] = "push"
