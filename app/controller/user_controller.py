"""
UserController - đăng ký, hồ sơ user hiện tại, và quản trị user (admin).

Public:
  - POST /api/register  -> tạo user mới, trả {message} (client tự gọi /login sau).

Cần đăng nhập:
  - GET  /api/me        -> thông tin user đang đăng nhập (kèm phone/address).
  - PUT  /api/me        -> tự cập nhật hồ sơ (email/phone/address).

Quản trị (theo quyền):
  - GET    /api/users          (view_users)               -> danh sách user phân trang.
  - GET    /api/users/count    (view_users)               -> tổng số user.
  - GET    /api/users/{id}     (view_user_details)        -> chi tiết user.
  - POST   /api/users          (create_user)              -> tạo user.
  - PUT    /api/users/{id}     (edit_user hoặc chính chủ) -> cập nhật user.
  - PATCH  /api/users/{id}/active (activate_deactivate_user) -> kích hoạt/khóa.
  - DELETE /api/users/{id}     (delete_user)              -> xóa user.
"""
from __future__ import annotations

import logging

from xime.adapters.web.routing import delete, get, patch, post, put
from xime.starters.mail import MailError

from app.dto.request.user_request import (
    ActiveStatusRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
from app.dto.response.token_response import CountResponse, MessageResponse
from app.dto.response.user_response import UserResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.auth_token_service import AuthTokenService
from app.service.authorization_service import AuthorizationService
from app.service.email_service import EmailService
from app.service.user_service import UserService

logger = logging.getLogger(__name__)


class UserController:
    prefix = "/api"
    tags = ["users"]

    def __init__(
        self,
        user_service: UserService,
        authorization_service: AuthorizationService,
        auth_token_service: AuthTokenService,
        email_service: EmailService,
    ) -> None:
        self._user_svc = user_service
        self._authz = authorization_service
        self._tokens = auth_token_service
        self._email = email_service

    # ── Public: registration ─────────────────────────────────────────────────

    @post("/register", status_code=201)
    async def register(self, body: RegisterRequest) -> MessageResponse:
        # Public self-registration; client redirects to /login afterwards.
        # Tự đăng ký công khai; client tự chuyển sang /login sau khi tạo.
        user = await self._user_svc.create_user(body.model_dump())
        # Gửi email xác minh (không bắt buộc - đăng ký vẫn thành công nếu email lỗi/chưa cấu hình)
        try:
            token = await self._tokens.create_verify_email(user.id)
            await self._email.send_verify_email(user.email, token)
        except MailError:
            logger.info("Bỏ qua gửi email xác minh (SMTP chưa cấu hình hoặc lỗi) cho %s", user.email)
        return MessageResponse(message="Đăng ký thành công. Vui lòng đăng nhập.")

    # ── Self-service profile ─────────────────────────────────────────────────

    @get("/me")
    async def me(self) -> UserResponse:
        # Current user incl. phone/address (access token only has uid/username/email).
        # User hiện tại kèm phone/address (access token chỉ có uid/username/email).
        user = require_login()
        db_user = await self._user_svc.get_user_by_id(user.id)
        if not db_user:
            raise AppException("E1004")
        return UserResponse.model_validate(db_user)

    @get("/me/permissions")
    async def my_permissions(self) -> list[str]:
        # Effective permissions of the current user, for FE admin-menu gating.
        # Quyền hiệu lực của user hiện tại, để FE ẩn/hiện menu admin.
        user = require_login()
        return await self._authz.get_effective_permissions(user)

    @put("/me")
    async def update_me(self, body: ProfileUpdateRequest) -> UserResponse:
        # Self-service profile update.
        # Tự cập nhật hồ sơ của chính mình.
        user = require_login()
        updated = await self._user_svc.update_profile(
            user.id, body.model_dump(exclude_unset=True)
        )
        return UserResponse.model_validate(updated)

    # ── Admin: user management ───────────────────────────────────────────────

    @get("/users")
    async def list_users(self, page: int = 1, limit: int = 10) -> list[UserResponse]:
        user = require_login()
        await self._authz.require(user, "view_users")
        users = await self._user_svc.get_users_paginated(page, limit)
        return [UserResponse.model_validate(u) for u in users]

    @get("/users/count")
    async def count_users(self) -> CountResponse:
        user = require_login()
        await self._authz.require(user, "view_users")
        return CountResponse(total=await self._user_svc.count_users())

    @get("/users/{id}")
    async def user_detail(self, id: int) -> UserResponse:
        user = require_login()
        await self._authz.require(user, "view_user_details", target_id=id)
        db_user = await self._user_svc.get_user_by_id(id)
        if not db_user:
            raise AppException("E1004")
        return UserResponse.model_validate(db_user)

    @post("/users", status_code=201)
    async def create_user(self, body: UserCreateRequest) -> UserResponse:
        user = require_login()
        await self._authz.require(user, "create_user")
        created = await self._user_svc.create_user(body.model_dump())
        return UserResponse.model_validate(created)

    @put("/users/{id}")
    async def update_user(self, id: int, body: UserUpdateRequest) -> UserResponse:
        # Admin edit, or the user editing themselves (mirrors PHP edit_user || self).
        # Admin sửa, hoặc user tự sửa mình (giống PHP edit_user || chính chủ).
        user = require_login()
        is_self = user.id == id
        await self._authz.require(user, "edit_user", target_id=id, is_user_owned=is_self)
        updated = await self._user_svc.update_user(
            id, body.model_dump(exclude_unset=True)
        )
        return UserResponse.model_validate(updated)

    @patch("/users/{id}/active")
    async def set_active(self, id: int, body: ActiveStatusRequest) -> UserResponse:
        user = require_login()
        await self._authz.require(user, "activate_deactivate_user", target_id=id)
        updated = await self._user_svc.set_user_active(id, body.is_active)
        return UserResponse.model_validate(updated)

    @delete("/users/{id}")
    async def remove_user(self, id: int) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_user")
        await self._user_svc.delete_user(id)
        return MessageResponse(message="User deleted")
