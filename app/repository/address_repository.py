from __future__ import annotations

from sqlalchemy import select, update

from app.entity.user_address import UserAddress
from xime.starters.sqlalchemy import CrudRepository


class AddressRepository(CrudRepository[UserAddress]):
    model = UserAddress

    async def find_by_user_id(self, user_id: int) -> list[UserAddress]:
        # Địa chỉ của một user, mặc định lên đầu rồi mới tới mới nhất
        result = await self.session.execute(
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .order_by(UserAddress.is_default.desc(), UserAddress.id.desc())
        )
        return list(result.scalars().all())

    async def clear_default(self, user_id: int) -> None:
        # Gỡ cờ mặc định ở mọi địa chỉ của user (trước khi đặt mặc định mới)
        # Unset is_default on all of the user's addresses
        await self.session.execute(
            update(UserAddress)
            .where(UserAddress.user_id == user_id, UserAddress.is_default == True)  # noqa: E712
            .values(is_default=False)
        )

    async def count_by_user(self, user_id: int) -> int:
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count())
            .select_from(UserAddress)
            .where(UserAddress.user_id == user_id)
        )
        return int(result.scalar_one())
