from __future__ import annotations

from pydantic import BaseModel, Field


class EmailTestRequest(BaseModel):
    """Gửi một email thử tới địa chỉ chỉ định (admin test SMTP thủ công)."""

    # Dùng str (không EmailStr) để khỏi phụ thuộc package email-validator
    to: str = Field(min_length=3, max_length=255)
    subject: str = Field(default="Email thử từ Shop", max_length=255)
    message: str = Field(default="Đây là email thử nghiệm cấu hình SMTP.", max_length=2000)
