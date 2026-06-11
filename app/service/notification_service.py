import logging

from xime.core.transaction.manager import TransactionManager

from app.entity.notification import Notification
from app.exception.app_exception import AppException
from app.repository.notification_repository import NotificationRepository
from app.service.user_service import UserService

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        transaction: TransactionManager,
        notification_repository: NotificationRepository,
        user_service: UserService,
    ) -> None:
        self._transaction = transaction
        self._repo = notification_repository
        self._user_svc = user_service

    async def get_all_notifications(self) -> list[Notification]:
        async with self._transaction():
            return await self._repo.find_all_notifications()

    async def get_unread_notifications(self) -> list[Notification]:
        async with self._transaction():
            return await self._repo.find_unread_notifications()

    async def get_notification_by_id(self, notification_id: int) -> Notification | None:
        async with self._transaction():
            return await self._repo.find(notification_id)

    async def create_notification(self, data: dict) -> Notification:
        user = await self._user_svc.get_user_by_id(data["userId"])
        if not user:
            raise AppException("E1004")

        async with self._transaction():
            notif = Notification(
                user_id=user.id,
                title=data["title"],
                message=data.get("message"),
                type=data.get("type", "push"),
            )
            notif = await self._repo.save(notif)

        # Send email if type is 'email' (PHP behaviour: log only, no real SMTP here)
        # Gửi email nếu loại thông báo là email (giữ logic PHP, chỉ log, chưa gửi thật)
        if notif.type == "email":
            logger.info(
                "Email notification queued for user %s: %s",
                user.email,
                notif.title,
            )

        return notif

    async def mark_as_read(self, notification_id: int) -> Notification:
        from datetime import datetime, timezone

        async with self._transaction():
            notif = await self._repo.find(notification_id)
            if not notif:
                raise AppException("E10200")
            notif.is_read = True
            notif.read_at = datetime.now(timezone.utc)
            return await self._repo.save(notif)

    async def mark_all_as_read(self) -> int:
        async with self._transaction():
            return await self._repo.mark_all_as_read()

    async def delete_read_notifications(self) -> int:
        async with self._transaction():
            return await self._repo.delete_read_notifications()

    async def delete_notification(self, notification_id: int) -> None:
        async with self._transaction():
            notif = await self._repo.find(notification_id)
            if not notif:
                raise AppException("E10200")
            await self._repo.delete(notif)
