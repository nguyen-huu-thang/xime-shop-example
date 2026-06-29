# Gỡ `ShopWebAdapter`, chuyển sang API `configure_*` của Xime

> Thực hiện 2026-06-29. Mục đích: ghi lại để phiên sau biết hiện trạng wiring web layer.

## Tóm tắt

Trước đây shop **subclass `WebAdapter`** (`app/shop_web_adapter.py`) để gắn exception handler,
`JwtMiddleware` và CORS - vì framework Xime chưa có hook public (xem issue-002 cũ, đã đóng).
Framework Xime nay đã bổ sung API hạng nhất nên **đã gỡ adapter tự viết**:

- `configure_cors(...)` - bật CORS, tự đọc khối `cors.*` trong `application.yml`.
- `configure_middleware(MW, opt=Inject(Type), ...)` - đăng ký middleware, lấy dependency từ DI
  container qua marker `Inject(...)` (và `FromConfig("a.b", default)` nếu cần đọc YAML).
- `configure_exception_handlers({ExcType: handler})` - đăng ký exception handler toàn cục.

Cả ba gọi trong [`app/config/web.py`](../../app/config/web.py). Framework tự nạp `config/web.py`
lúc bootstrap (import mọi sibling của `config/dependency`), nên `main.py` chỉ cần `WebAdapter()`.

## Cách wiring hiện tại (đọc khi cần sửa web layer)

File [`app/config/web.py`](../../app/config/web.py) khai báo, **theo đúng thứ tự**:

1. `configure_controllers("app.controller")`
2. `configure_cors(allow_credentials=True, allow_methods=["*"], allow_headers=["*"])`
   - `allow_origins` / `allow_origin_regex` để mặc định (None) -> đọc từ `cors.*` trong YAML.
   - **Phải đứng TRƯỚC** `configure_middleware(JwtMiddleware)`: middleware khai báo trước =
     lớp ngoài hơn -> preflight `OPTIONS` xử lý trước khi xác thực JWT.
3. `configure_middleware(JwtMiddleware, auth_svc=Inject(...), user_svc=Inject(...), blacklist_svc=Inject(...))`
4. `configure_exception_handlers({AppException: ..., RequestValidationError: ...})`
5. `configure_openapi(OpenApiConfig(...))`

Thứ tự middleware cuối cùng (ngoài -> trong): `RequestContextMiddleware` (framework, ngoài cùng)
-> `CORSMiddleware` -> `JwtMiddleware` -> handler.

## File liên quan

- [`app/config/web.py`](../../app/config/web.py) - nơi wiring.
- [`app/exception/handler.py`](../../app/exception/handler.py) - 2 handler public:
  `app_exception_handler`, `validation_exception_handler` (đã bỏ `register_exception_handlers`).
- [`app/security/jwt_middleware.py`](../../app/security/jwt_middleware.py) - pure-ASGI, không đổi.
- [`docs/luu-y-cau-hinh-cors.md`](luu-y-cau-hinh-cors.md) - lưu ý CORS + cookie cross-site.

## Đã xóa

- `app/shop_web_adapter.py` (không còn cần subclass).
- `.claude/framework-issues/issue-002-no-exception-handler-hook.md` (framework đã giải quyết).

## Test

`python -m pytest test/` -> **50 passed**. Test build app qua `WebAdapter().build_app(test_app)`
(không còn `ShopWebAdapter`); registry được nạp nhờ dòng `import app.config.web  # side effect`
sẵn có trong các file test.

Tiện thể vá 1 bug test có sẵn: `test_7_12_wishlist_flow` assert sai key (`id` -> `productId`,
khớp shape thật của `GET /api/wishlist`).
