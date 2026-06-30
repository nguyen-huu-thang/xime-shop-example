from __future__ import annotations

from xime.adapters.web.routing import delete, get, patch, post

from app.dto.request.notification_request import (
    NotificationBroadcastRequest,
    NotificationCreateRequest,
)
from app.dto.response.notification_response import (
    NotificationResponse,
    UnreadCountResponse,
)
from app.dto.response.token_response import MessageResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.notification_service import NotificationService


class NotificationController:
    prefix = "/api/notifications"
    tags = ["notifications"]

    def __init__(
        self,
        notification_service: NotificationService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = notification_service
        self._authz = authorization_service

    @get("")
    async def list(self) -> list[NotificationResponse]:
        user = require_login()
        await self._authz.require(user, "view_notifications")
        notifs = await self._svc.get_all_notifications()
        return [NotificationResponse.model_validate(n) for n in notifs]

    @get("/unread")
    async def unread(self) -> list[NotificationResponse]:
        user = require_login()
        await self._authz.require(user, "view_notifications")
        notifs = await self._svc.get_unread_notifications()
        return [NotificationResponse.model_validate(n) for n in notifs]

    # ── Hộp thư người dùng (per-user inbox) ─────────────────────────────────────
    # Khai báo TRƯỚC /{id} để "/me" không bị khớp nhầm vào route path param.

    @get("/me")
    async def my_notifications(
        self, page: int = 1, limit: int = 20
    ) -> list[NotificationResponse]:
        user = require_login()
        notifs = await self._svc.get_my_notifications(user.id, page, limit)
        return [NotificationResponse.model_validate(n) for n in notifs]

    @get("/me/unread-count")
    async def my_unread_count(self) -> UnreadCountResponse:
        user = require_login()
        return UnreadCountResponse(count=await self._svc.count_my_unread(user.id))

    @patch("/me/read-all")
    async def my_read_all(self) -> dict:
        user = require_login()
        count = await self._svc.mark_all_my_read(user.id)
        return {"updated": count}

    @get("/{id}")
    async def detail(self, id: int) -> NotificationResponse:
        user = require_login()
        await self._authz.require(user, "view_notifications")
        notif = await self._svc.get_notification_by_id(id)
        if not notif:
            raise AppException("E10330")
        return NotificationResponse.model_validate(notif)

    @post("", status_code=201)
    async def create(self, body: NotificationCreateRequest) -> NotificationResponse:
        user = require_login()
        await self._authz.require(user, "create_notification")
        data = body.model_dump(by_alias=True)
        notif = await self._svc.create_notification(data)
        return NotificationResponse.model_validate(notif)

    @post("/broadcast")
    async def broadcast(self, body: NotificationBroadcastRequest) -> dict:
        # Admin gửi thông báo tới tất cả user đang hoạt động.
        user = require_login()
        await self._authz.require(user, "create_notification")
        count = await self._svc.broadcast(body.title, body.message, body.link)
        return {"sent": count}

    @patch("/{id}/read")
    async def mark_as_read(self, id: int) -> NotificationResponse:
        # Owner-only: chỉ chủ thông báo mới đánh dấu đã đọc (vá IDOR)
        user = require_login()
        notif = await self._svc.mark_as_read(id, user.id)
        return NotificationResponse.model_validate(notif)

    @patch("/read-all")
    async def mark_all_read(self) -> dict:
        user = require_login()
        await self._authz.require(user, "view_notifications")
        count = await self._svc.mark_all_as_read()
        return {"updated": count}

    @delete("/read")
    async def delete_read(self) -> dict:
        user = require_login()
        await self._authz.require(user, "delete_notification")
        count = await self._svc.delete_read_notifications()
        return {"deleted": count}

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_notification")
        await self._svc.delete_notification(id)
        return MessageResponse(message="Notification deleted")
