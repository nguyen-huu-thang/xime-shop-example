from __future__ import annotations

from pydantic import BaseModel

from app.entity.user_address import UserAddress


class AddressResponse(BaseModel):
    id: int
    recipientName: str
    recipientPhone: str
    province: str
    district: str
    ward: str
    detail: str
    lat: float | None = None
    lng: float | None = None
    isDefault: bool

    @classmethod
    def from_entity(cls, a: UserAddress) -> "AddressResponse":
        return cls(
            id=a.id,
            recipientName=a.recipient_name,
            recipientPhone=a.recipient_phone,
            province=a.province,
            district=a.district,
            ward=a.ward,
            detail=a.detail,
            lat=float(a.lat) if a.lat is not None else None,
            lng=float(a.lng) if a.lng is not None else None,
            isDefault=a.is_default,
        )
