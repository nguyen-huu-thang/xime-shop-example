from datetime import datetime, timezone

from sqlalchemy import delete, select, update

from app.entity.notification import Notification
from xime.starters.sqlalchemy import CrudRepository


class NotificationRepository(CrudRepository[Notification]):
    model = Notification

    async def find_all_notifications(self) -> list[Notification]:
        # Return all notifications ordered by created_at desc
        # Trả về tất cả thông báo, mới nhất trước
        result = await self.session.execute(
            select(Notification).order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_unread_notifications(self) -> list[Notification]:
        result = await self.session.execute(
            select(Notification).where(Notification.is_read == False)  # noqa: E712
        )
        return list(result.scalars().all())

    async def mark_all_as_read(self) -> int:
        # Bulk update: set is_read=True, read_at=now for all unread
        # Cập nhật hàng loạt: đánh dấu tất cả chưa đọc là đã đọc
        result = await self.session.execute(
            update(Notification)
            .where(Notification.is_read == False)  # noqa: E712
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        return result.rowcount

    async def delete_read_notifications(self) -> int:
        # Bulk delete all read notifications
        # Xóa hàng loạt tất cả thông báo đã đọc
        result = await self.session.execute(
            delete(Notification).where(Notification.is_read == True)  # noqa: E712
        )
        return result.rowcount
