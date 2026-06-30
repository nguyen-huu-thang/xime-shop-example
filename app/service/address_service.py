"""
AddressService - sổ địa chỉ giao hàng của người dùng (checkout Phase 1).

Mỗi user có nhiều địa chỉ, tối đa một địa chỉ is_default=True. Mọi thao tác sửa/xóa/đặt
mặc định chỉ trên địa chỉ của chính user (kiểm tra ownership trong service).
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.user_address import UserAddress
from app.exception.app_exception import AppException
from app.repository.address_repository import AddressRepository


class AddressService:
    def __init__(
        self,
        transaction: TransactionManager,
        address_repository: AddressRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = address_repository

    async def get_my_addresses(self, user_id: int) -> list[UserAddress]:
        async with self._transaction():
            return await self._repo.find_by_user_id(user_id)

    async def get_owned_address(self, address_id: int, user_id: int) -> UserAddress:
        """Lấy địa chỉ thuộc về user; không thấy hoặc không phải của user -> E10320.
        Trả về E10320 (không tìm thấy) cả khi không phải chủ để tránh lộ tồn tại bản ghi.
        """
        async with self._transaction():
            addr = await self._repo.find(address_id)
            if not addr or addr.user_id != user_id:
                raise AppException("E10320")
            return addr

    async def create_address(self, user_id: int, data: dict) -> UserAddress:
        async with self._transaction():
            # First address, or explicitly requested -> becomes default
            # Địa chỉ đầu tiên, hoặc yêu cầu rõ -> đặt làm mặc định
            existing_count = await self._repo.count_by_user(user_id)
            make_default = bool(data.get("is_default")) or existing_count == 0
            if make_default:
                await self._repo.clear_default(user_id)

            addr = UserAddress(
                user_id=user_id,
                recipient_name=data["recipient_name"],
                recipient_phone=data["recipient_phone"],
                province=data["province"],
                district=data["district"],
                ward=data["ward"],
                detail=data["detail"],
                lat=data.get("lat"),
                lng=data.get("lng"),
                is_default=make_default,
            )
            return await self._repo.save(addr)

    async def update_address(
        self, address_id: int, user_id: int, data: dict
    ) -> UserAddress:
        async with self._transaction():
            addr = await self._repo.find(address_id)
            if not addr or addr.user_id != user_id:
                raise AppException("E10320")

            # Chỉ cập nhật field được gửi (partial update)
            for field in (
                "recipient_name",
                "recipient_phone",
                "province",
                "district",
                "ward",
                "detail",
                "lat",
                "lng",
            ):
                if field in data and data[field] is not None:
                    setattr(addr, field, data[field])

            # Đặt mặc định nếu yêu cầu rõ là True
            if data.get("is_default") is True and not addr.is_default:
                await self._repo.clear_default(user_id)
                addr.is_default = True

            return await self._repo.save(addr)

    async def set_default(self, address_id: int, user_id: int) -> UserAddress:
        async with self._transaction():
            addr = await self._repo.find(address_id)
            if not addr or addr.user_id != user_id:
                raise AppException("E10320")
            await self._repo.clear_default(user_id)
            addr.is_default = True
            return await self._repo.save(addr)

    async def delete_address(self, address_id: int, user_id: int) -> None:
        async with self._transaction():
            addr = await self._repo.find(address_id)
            if not addr or addr.user_id != user_id:
                raise AppException("E10320")
            await self._repo.delete(addr)
