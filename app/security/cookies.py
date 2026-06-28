"""
Tiện ích cookie cho refresh token.

Chiến lược bảo mật (chốt với người dùng):
  - Access token: client lưu trong RAM, gắn header Authorization: Bearer.
  - Refresh token: lưu trong httpOnly cookie, Path=/api/refresh-token -> trình duyệt CHỈ
    gửi cookie này tới đúng endpoint refresh, các endpoint khác không nhận được (JS cũng
    không đọc được vì httpOnly).

Path-scoping (Path=/api/refresh-token) là điểm mấu chốt: mọi request tới /api/* khác sẽ
không kèm cookie refresh, giảm bề mặt rò rỉ.
"""
from __future__ import annotations

from fastapi import Response

# Tên cookie + path giới hạn tới đúng endpoint refresh.
# Cookie name + path scoped to the refresh endpoint only.
REFRESH_COOKIE_NAME = "refreshToken"
REFRESH_COOKIE_PATH = "/api/refresh-token"


def set_refresh_cookie(
    response: Response,
    refresh_token: str,
    max_age: int,
    secure: bool,
    samesite: str,
) -> None:
    """Đặt refresh token vào httpOnly cookie, giới hạn path tới endpoint refresh."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response, secure: bool, samesite: str) -> None:
    """Xóa refresh cookie (khi logout). Phải khớp path để trình duyệt xóa đúng cookie."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite=samesite,
    )
