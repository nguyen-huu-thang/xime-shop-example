import logging

from xime.core.transaction.manager import TransactionManager

from app.entity.notification import Notification
from app.exception.app_exception import AppException
from app.repository.notification_repository import NotificationRepository
from app.service.email_service import EmailService
from app.service.user_service import UserService

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        transaction: TransactionManager,
        notification_repository: NotificationRepository,
        user_service: UserService,
        email_service: EmailService,
    ) -> None:
        self._transaction = transaction
        self._repo = notification_repository
        self._user_svc = user_service
        self._email = email_service

    async def get_all_notifications(self) -> list[Notification]:
        async with self._transaction():
            return await self._repo.find_all_notifications()

    async def get_unread_notifications(self) -> list[Notification]:
        async with self._transaction():
            return await self._repo.find_unread_notifications()

    # ── Hộp thư theo người dùng (per-user inbox) ────────────────────────────────

    async def get_my_notifications(
        self, user_id: int, page: int, limit: int
    ) -> list[Notification]:
        async with self._transaction():
            return await self._repo.find_by_user_id(user_id, page, limit)

    async def count_my_unread(self, user_id: int) -> int:
        async with self._transaction():
            return await self._repo.count_unread_by_user(user_id)

    async def mark_all_my_read(self, user_id: int) -> int:
        async with self._transaction():
            return await self._repo.mark_all_read_by_user(user_id)

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
                link=data.get("link"),
            )
            notif = await self._repo.save(notif)

        # Send email if type is 'email' (PHP behaviour: log only, no real SMTP here)
        # Gửi email nếu loại thông báo là email (giữ logic PHP, chỉ log, chưa gửi thật)
        # TODO(email): nối gửi SMTP thật khi có email starter (framework-issues/issue-005).
        if notif.type == "email":
            logger.info(
                "Email notification queued for user %s: %s",
                user.email,
                notif.title,
            )

        return notif

    # ── Helper tự sinh thông báo theo sự kiện ───────────────────────────────────

    async def notify(
        self,
        user_id: int,
        title: str,
        message: str | None = None,
        link: str | None = None,
        also_email: bool = False,
        email_to: str | None = None,
    ) -> None:
        """Create an in-app notification (type='push') for an event. Fault-tolerant:
        a failure here must NOT break the calling business flow (order, shipping...).
        Tạo thông báo in-app cho một sự kiện. Nuốt lỗi non-critical (chỉ log) để không
        làm hỏng nghiệp vụ gọi nó (đặt hàng, đổi trạng thái giao...).

        also_email=True (Phase B): gửi kèm email thông báo (NỀN, fault-tolerant). Nếu không
        truyền email_to, tự tra email của user. Lỗi email không ảnh hưởng thông báo in-app.
        """
        try:
            async with self._transaction():
                await self._repo.save(
                    Notification(
                        user_id=user_id,
                        title=title,
                        message=message,
                        type="push",
                        link=link,
                    )
                )
        except Exception:  # noqa: BLE001 - thông báo là phụ, không được làm hỏng nghiệp vụ chính
            logger.exception("Không thể tạo thông báo cho user %s: %s", user_id, title)

        if also_email:
            try:
                to = email_to
                if not to:
                    user = await self._user_svc.get_user_by_id(user_id)
                    to = user.email if user else None
                if to:
                    await self._email.send_notification(to, title, message, link)
            except Exception:  # noqa: BLE001 - email là phụ, không làm hỏng nghiệp vụ chính
                logger.exception("Không thể gửi email thông báo cho user %s: %s", user_id, title)

    async def broadcast(
        self, title: str, message: str | None = None, link: str | None = None
    ) -> int:
        """Admin gửi một thông báo in-app tới TẤT CẢ user đang hoạt động.
        Trả về số thông báo đã tạo. Tạo trong một transaction.
        """
        user_ids = await self._user_svc.get_all_active_user_ids()
        if not user_ids:
            return 0
        # Chèn theo lô (save_all) thay vì save() từng cái -> nhanh hơn khi nhiều user.
        # Bulk insert instead of one save() per user -> much faster for many users.
        async with self._transaction():
            await self._repo.save_all(
                [
                    Notification(
                        user_id=uid,
                        title=title,
                        message=message,
                        type="push",
                        link=link,
                    )
                    for uid in user_ids
                ]
            )
        return len(user_ids)

    async def mark_as_read(self, notification_id: int, user_id: int) -> Notification:
        """Mark a notification read. Only the owner may do so (fix IDOR).
        Đánh dấu đã đọc; chỉ chủ sở hữu được phép (vá IDOR).
        """
        from datetime import datetime, timezone

        async with self._transaction():
            notif = await self._repo.find(notification_id)
            if not notif:
                raise AppException("E10330")
            if notif.user_id != user_id:
                raise AppException("E10331")
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
                raise AppException("E10330")
            await self._repo.delete(notif)
