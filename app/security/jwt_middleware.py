"""
JwtMiddleware — xác thực Bearer JWT cho mỗi request.
Port từ JwtAuthenticatorListener.php.

Logic:
  - Không có header Authorization → bỏ qua (request ẩn danh)
  - Header không bắt đầu "Bearer " → 401 E1023
  - Mọi lỗi trong quá trình xác thực → 401 E1023 (giống PHP)
"""
from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.security.current_user import set_current_user
from app.service.authentication_service import AuthenticationService
from app.service.blacklist_token_service import BlacklistTokenService
from app.service.user_service import UserService

_E1023_BODY = {"errorKey": "E1023", "code": 1023, "message": "Không thể xác thực"}


class JwtMiddleware(BaseHTTPMiddleware):
    """Validate Bearer JWT → check blacklist → load user into security context.
    Xác thực JWT → kiểm tra blacklist → nạp user vào security context.
    """

    def __init__(
        self,
        app,
        auth_svc: AuthenticationService,
        user_svc: UserService,
        blacklist_svc: BlacklistTokenService,
    ) -> None:
        super().__init__(app)
        self._auth_svc = auth_svc
        self._user_svc = user_svc
        self._blacklist_svc = blacklist_svc

    async def dispatch(self, request: Request, call_next) -> Response:
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            # Anonymous request — pass through; controller decides if login is needed
            # Request ẩn danh — tiếp tục; controller quyết định có cần đăng nhập không
            return await call_next(request)

        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content=_E1023_BODY)

        jwt_str = auth_header[7:]
        try:
            claims = self._auth_svc.validate_token(jwt_str)

            # Reject blacklisted tokens (e.g. after logout)
            # Từ chối token đã bị thu hồi (ví dụ sau khi đăng xuất)
            token_id: str = claims["jti"]
            if await self._blacklist_svc.is_blacklisted(token_id):
                return JSONResponse(status_code=401, content=_E1023_BODY)

            # Only access tokens are allowed in Authorization header
            # Chỉ chấp nhận access token trong header Authorization
            if claims.get("type") != "access":
                return JSONResponse(status_code=401, content=_E1023_BODY)

            uid: int = claims["uid"]
            user = await self._user_svc.get_user_by_id(uid)
            if not user or not user.is_active:
                return JSONResponse(status_code=401, content=_E1023_BODY)

            set_current_user(user, jwt_str)

        except Exception:
            # Any unexpected error during auth → generic 401 (same as PHP catch-all)
            # Mọi lỗi không mong đợi khi xác thực → 401 chung (giống PHP catch-all)
            return JSONResponse(status_code=401, content=_E1023_BODY)

        return await call_next(request)
