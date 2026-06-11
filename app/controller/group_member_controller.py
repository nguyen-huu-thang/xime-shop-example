from __future__ import annotations

from xime.adapters.web.routing import get, post

from app.dto.request.group_member_request import (
    GroupMemberAddRequest,
    GroupMemberCheckRequest,
    GroupMemberRemoveRequest,
)
from app.dto.response.group_response import GroupMemberResponse, GroupResponse
from app.dto.response.token_response import MessageResponse
from app.dto.response.user_response import UserResponse
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.group_member_service import GroupMemberService


class GroupMemberController:
    prefix = "/api/group-member"
    tags = ["group-members"]

    def __init__(
        self,
        group_member_service: GroupMemberService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = group_member_service
        self._authz = authorization_service

    @post("/add", status_code=201)
    async def add_user_to_group(self, body: GroupMemberAddRequest) -> dict:
        user = require_login()
        await self._authz.require(user, "manage_group_members")
        member = await self._svc.add_user_to_group(body.user_id, body.group_id)
        return {
            "message": "User added to group successfully",
            "group_member": GroupMemberResponse.model_validate(member).model_dump(),
        }

    @post("/remove")
    async def remove_user_from_group(self, body: GroupMemberRemoveRequest) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "manage_group_members")
        await self._svc.remove_user_from_group(body.user_id, body.group_id)
        return MessageResponse(message="User removed from group successfully")

    @get("/user/groups")
    async def get_groups_for_current_user(self) -> list[GroupResponse]:
        user = require_login()
        await self._authz.require(user, "view_group_details")
        groups = await self._svc.find_groups_by_user(user)
        return [GroupResponse.model_validate(g) for g in groups]

    @get("/user_{id}/groups")
    async def get_groups_for_user(self, id: int) -> list[GroupResponse]:
        user = require_login()
        await self._authz.require(user, "view_group_details")
        groups = await self._svc.get_groups_by_user(id)
        return [GroupResponse.model_validate(g) for g in groups]

    @get("/group_{id}/users")
    async def get_users_in_group(self, id: int) -> list[UserResponse]:
        user = require_login()
        await self._authz.require(user, "view_group_details")
        users = await self._svc.get_users_in_group(id)
        return [UserResponse.model_validate(u) for u in users]

    @post("/check")
    async def is_user_in_group(self, body: GroupMemberCheckRequest) -> dict:
        user = require_login()
        await self._authz.require(user, "view_group_details")
        result = await self._svc.is_user_in_group(body.user_id, body.group_id)
        return {"is_in_group": result}
