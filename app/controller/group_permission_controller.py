from __future__ import annotations

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.permission_request import (
    AssignGroupPermissionRequest,
    CheckPermissionRequest,
    DeleteGroupPermissionRequest,
    UpdateGroupPermissionRequest,
)
from app.dto.response.token_response import MessageResponse
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.group_permission_service import GroupPermissionService
from app.service.group_service import GroupService


class GroupPermissionController:
    prefix = "/api/group-permissions"
    tags = ["group-permissions"]

    def __init__(
        self,
        group_permission_service: GroupPermissionService,
        group_service: GroupService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = group_permission_service
        self._group_svc = group_service
        self._authz = authorization_service

    @post("", status_code=201)
    async def assign_permission(self, body: AssignGroupPermissionRequest) -> list[dict]:
        user = require_login()
        await self._authz.require(user, "create_permission")
        perms_dict = {k: v.model_dump() for k, v in body.permissions.items()}
        return await self._svc.assign_permissions(body.group_id, perms_dict)

    @get("/{group_id}")
    async def get_permissions_by_group(self, group_id: int) -> list:
        user = require_login()
        await self._authz.require(user, "view_permissions")
        group = await self._group_svc.get_group_by_id(group_id)
        return await self._svc.get_permissions_by_group(group)

    @put("")
    async def update_permission(self, body: UpdateGroupPermissionRequest) -> list[dict]:
        user = require_login()
        await self._authz.require(user, "edit_permission")
        perms_dict = {k: v.model_dump() for k, v in body.permissions.items()}
        return await self._svc.update_permission(body.group_id, perms_dict)

    @post("/check")
    async def has_permission(self, body: dict) -> dict:
        user = require_login()
        await self._authz.require(user, "view_permissions")
        group_id = body.get("group_id")
        permission_name = body.get("permission_name")
        target_id = body.get("target_id")
        # Endpoint kiểm tra grant thô theo đúng target (không resolve cây category)
        # Raw-grant introspection against the exact target (no category-tree resolution)
        scope_ids = {target_id} if target_id is not None else set()
        result = await self._svc.has_permission(group_id, permission_name, scope_ids)
        return {"has_permission": result}

    @delete("")
    async def delete_permission(self, body: DeleteGroupPermissionRequest) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_permission")
        await self._svc.delete_permissions(body.group_id, body.permissions)
        return MessageResponse(message="Permissions deleted successfully.")
