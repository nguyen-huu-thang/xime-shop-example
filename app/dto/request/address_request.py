from __future__ import annotations

from pydantic import BaseModel, Field


class AddressCreateRequest(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=100, alias="recipientName")
    recipient_phone: str = Field(min_length=6, max_length=20, alias="recipientPhone")
    province: str = Field(min_length=1, max_length=100)
    district: str = Field(min_length=1, max_length=100)
    ward: str = Field(min_length=1, max_length=100)
    detail: str = Field(min_length=1, max_length=255)
    # Coordinates optional (demo map); range hợp lệ của vĩ độ/kinh độ
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    is_default: bool = Field(default=False, alias="isDefault")

    model_config = {"populate_by_name": True}


class AddressUpdateRequest(BaseModel):
    recipient_name: str | None = Field(default=None, min_length=1, max_length=100, alias="recipientName")
    recipient_phone: str | None = Field(default=None, min_length=6, max_length=20, alias="recipientPhone")
    province: str | None = Field(default=None, min_length=1, max_length=100)
    district: str | None = Field(default=None, min_length=1, max_length=100)
    ward: str | None = Field(default=None, min_length=1, max_length=100)
    detail: str | None = Field(default=None, min_length=1, max_length=255)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    is_default: bool | None = Field(default=None, alias="isDefault")

    model_config = {"populate_by_name": True}
