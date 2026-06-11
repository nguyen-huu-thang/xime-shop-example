from __future__ import annotations

from xime.adapters.web.routing import delete, get, patch, post

from app.dto.request.notification_request import NotificationCreateRequest
from app.dto.response.notification_response import NotificationResponse
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

    @get("/{id}")
    async def detail(self, id: int) -> NotificationResponse:
        user = require_login()
        await self._authz.require(user, "view_notifications")
        notif = await self._svc.get_notification_by_id(id)
        if not notif:
            raise AppException("E10200")
        return NotificationResponse.model_validate(notif)

    @post("", status_code=201)
    async def create(self, body: NotificationCreateRequest) -> NotificationResponse:
        user = require_login()
        await self._authz.require(user, "create_notification")
        data = body.model_dump(by_alias=True)
        notif = await self._svc.create_notification(data)
        return NotificationResponse.model_validate(notif)

    @patch("/{id}/read")
    async def mark_as_read(self, id: int) -> NotificationResponse:
        require_login()
        notif = await self._svc.mark_as_read(id)
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
