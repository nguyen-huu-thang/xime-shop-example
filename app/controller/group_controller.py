from __future__ import annotations

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.group_request import GroupCreateRequest, GroupUpdateRequest
from app.dto.response.group_response import GroupResponse
from app.dto.response.token_response import MessageResponse
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.group_service import GroupService


class GroupController:
    prefix = "/api/group"
    tags = ["groups"]

    def __init__(
        self,
        group_service: GroupService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = group_service
        self._authz = authorization_service

    @get("")
    async def list(self, page: int = 1, limit: int = 10) -> list[GroupResponse]:
        user = require_login()
        await self._authz.require(user, "view_groups")
        groups = await self._svc.get_paginated_groups(page, limit)
        return [GroupResponse.model_validate(g) for g in groups]

    @get("/{id}")
    async def detail(self, id: int) -> GroupResponse:
        group = await self._svc.get_group_by_id(id)
        return GroupResponse.model_validate(group)

    @post("", status_code=201)
    async def create(self, body: GroupCreateRequest) -> GroupResponse:
        user = require_login()
        await self._authz.require(user, "create_group")
        group = await self._svc.create_group(body.name, body.description)
        return GroupResponse.model_validate(group)

    @put("/{id}")
    async def update(self, id: int, body: GroupUpdateRequest) -> GroupResponse:
        user = require_login()
        await self._authz.require(user, "edit_group", target_id=id)
        group = await self._svc.update_group(id, body.model_dump(exclude_unset=True))
        return GroupResponse.model_validate(group)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_group", target_id=id)
        await self._svc.delete_group(id)
        return MessageResponse(message="Group deleted")
