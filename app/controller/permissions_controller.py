from __future__ import annotations

from xime.adapters.web.routing import get

from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.permission_service import PermissionService


class PermissionsController:
    prefix = "/api/permission"
    tags = ["permissions"]

    def __init__(
        self,
        permission_service: PermissionService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = permission_service
        self._authz = authorization_service

    @get("")
    async def list(self) -> list[str]:
        user = require_login()
        await self._authz.require(user, "view_permissions")
        return await self._svc.get_permission_names()
