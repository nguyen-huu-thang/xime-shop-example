"""
current_user - truy cập người dùng hiện tại của request (thay $request->attributes->get('user')).

Dùng SecurityContext của framework Xime (xime.core.security):
  - `identity`  : lưu User entity đang đăng nhập
  - `credentials`: lưu access token (JWT) thô
SecurityContext tự được dọn cuối mỗi request bởi RequestContextMiddleware
(clear_security()), nên không lo data bleeding giữa các request.

JWT middleware (Phase 3) gọi set_current_user() sau khi xác thực token.
Controller gọi current_user() / require_login().
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from xime.core.security import CredentialType, authenticate, credentials, identity

from app.exception.app_exception import AppException

if TYPE_CHECKING:
    from app.entity.user import User


def set_current_user(user: "User", jwt: str) -> None:
    """Middleware gọi sau khi xác thực token thành công."""
    authenticate(identity=user, credentials=jwt, credential_type=CredentialType.TOKEN)


def current_user() -> "User | None":
    """Người dùng hiện tại, hoặc None nếu request ẩn danh."""
    return identity.get()


def current_jwt() -> str | None:
    """Access token (JWT) thô của request hiện tại, nếu có."""
    return credentials.get()


def require_login() -> "User":
    """Trả về user hiện tại; raise E2025 nếu chưa đăng nhập."""
    user = current_user()
    if user is None:
        raise AppException("E2025")
    return user
