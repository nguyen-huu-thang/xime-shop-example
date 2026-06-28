from xime.adapters.web import configure_controllers
from xime.adapters.web.openapi import JwtBearer, OpenApiConfig, configure_openapi

# Đăng ký các package chứa controller (class có method @get/@post/...)
# Register packages containing controllers
configure_controllers("app.controller")

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
