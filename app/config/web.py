from fastapi.exceptions import RequestValidationError

from xime.adapters.web import (
    Inject,
    configure_controllers,
    configure_cors,
    configure_exception_handlers,
    configure_middleware,
)
from xime.adapters.web.openapi import JwtBearer, OpenApiConfig, configure_openapi

from app.exception.app_exception import AppException
from app.exception.handler import app_exception_handler, validation_exception_handler
from app.security.jwt_middleware import JwtMiddleware
from app.service.authentication_service import AuthenticationService
from app.service.blacklist_token_service import BlacklistTokenService
from app.service.user_service import UserService

# Đăng ký các package chứa controller (class có method @get/@post/...)
# Register packages containing controllers
configure_controllers("app.controller")

# CORS - đăng ký TRƯỚC JwtMiddleware để là lớp ngoài hơn: preflight OPTIONS được xử lý
# trước khi xác thực JWT. allow_origins / allow_origin_regex để None -> đọc từ khối
# cors.* trong application.yml (Operator chỉnh CORS qua YAML, không đụng code).
# CORS must be registered before JWT so preflight runs before auth.
configure_cors(
    allow_credentials=True,   # cho phép gửi cookie refresh + header Authorization
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT middleware - dependency lấy từ DI container qua marker Inject lúc build_app.
# JWT middleware - dependencies resolved from the DI container via Inject markers.
configure_middleware(
    JwtMiddleware,
    auth_svc=Inject(AuthenticationService),
    user_svc=Inject(UserService),
    blacklist_svc=Inject(BlacklistTokenService),
)

# Exception handler toàn cục - map AppException + lỗi validation sang JSON chuẩn.
# Global exception handlers.
configure_exception_handlers(
    {
        AppException: app_exception_handler,
        RequestValidationError: validation_exception_handler,
    }
)

# Cấu hình OpenAPI / Swagger UI với JWT Bearer auth
# Configure OpenAPI / Swagger UI with JWT Bearer auth
configure_openapi(
    OpenApiConfig(
        title="Shop Backend",
        version="1.0.0",
        description=(
            "**Shop Backend** - bản migrate từ PHP/Symfony sang Python trên framework Xime.\n\n"
            "Dự án tham chiếu/kiểm thử cho framework Xime (kiến trúc đa lớp).\n\n"
            "**Xác thực:** Đăng nhập qua `POST /api/login`, lấy `accessToken`,\n"
            "dán vào ô Authorize (Bearer) để gọi các API yêu cầu quyền."
        ),
        swagger_ui_title="Shop Backend - Swagger UI",
        security=JwtBearer(),
        public_paths=[
            "/api/login",
            "/api/register",
            "/api/refresh-token",
            "/api/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ],
    )
)
