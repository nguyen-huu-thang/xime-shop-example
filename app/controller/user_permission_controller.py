from __future__ import annotations

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.permission_request import (
    AssignUserPermissionRequest,
    DeleteUserPermissionRequest,
    UpdateUserPermissionRequest,
)
from app.dto.response.token_response import MessageResponse
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.user_permission_service import UserPermissionService
from app.service.user_service import UserService


class UserPermissionController:
    prefix = "/api/user-permissions"
    tags = ["user-permissions"]

    def __init__(
        self,
        user_permission_service: UserPermissionService,
        user_service: UserService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = user_permission_service
        self._user_svc = user_service
        self._authz = authorization_service

    @post("", status_code=201)
    async def assign_permission(self, body: AssignUserPermissionRequest) -> list[dict]:
        user = require_login()
        await self._authz.require(user, "create_permission")
        perms_dict = {k: v.model_dump() for k, v in body.permissions.items()}
        return await self._svc.assign_permissions(body.user_id, perms_dict)

    @get("/{user_id}")
    async def get_permissions_by_user(self, user_id: int) -> list:
        user = require_login()
        await self._authz.require(user, "view_permissions")
        return await self._svc.get_permissions_by_user_id(user_id)

    @put("")
    async def update_permission(self, body: UpdateUserPermissionRequest) -> list[dict]:
        user = require_login()
        await self._authz.require(user, "edit_permission")
        perms_dict = {k: v.model_dump() for k, v in body.permissions.items()}
        return await self._svc.update_permission(body.user_id, perms_dict)

    @post("/check")
    async def has_permission(self, body: dict) -> dict:
        user = require_login()
        await self._authz.require(user, "view_permissions")
        user_id = body.get("user_id")
        permission_name = body.get("permission_name")
        target_id = body.get("target_id")
        # Endpoint kiểm tra grant thô theo đúng target (không resolve cây category)
        # Raw-grant introspection against the exact target (no category-tree resolution)
        scope_ids = {target_id} if target_id is not None else set()
        result = await self._svc.has_permission(user_id, permission_name, scope_ids)
        return {"has_permission": result}

    @delete("")
    async def delete_permission(self, body: DeleteUserPermissionRequest) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_permission")
        await self._svc.delete_permissions(body.user_id, body.permissions)
        return MessageResponse(message="Permissions deleted successfully.")
