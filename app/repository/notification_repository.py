from datetime import datetime, timezone

from sqlalchemy import delete, select, update

from app.entity.notification import Notification
from app.utils.pagination import paginate
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

    # ── Hộp thư theo người dùng (per-user inbox) ────────────────────────────────

    async def find_by_user_id(
        self, user_id: int, page: int, limit: int
    ) -> list[Notification]:
        # Notifications of one user, newest first, paginated
        # Thông báo của một user, mới nhất trước, phân trang
        offset, limit = paginate(page, limit)
        result = await self.session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_unread_by_user(self, user_id: int) -> int:
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        )
        return int(result.scalar_one())

    async def mark_all_read_by_user(self, user_id: int) -> int:
        # Bulk update unread -> read for one user only
        # Đánh dấu đã đọc hàng loạt cho riêng một user
        result = await self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        return result.rowcount

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
