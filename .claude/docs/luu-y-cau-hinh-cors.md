# Lưu ý: cấu hình CORS + cookie cross-site cho frontend Next.js

> Viết ngày 2026-06-25 theo yêu cầu. Đây là **phụ thuộc bắt buộc** để frontend chạy được.

## Vì sao cần

Frontend shop (Next.js) **không dùng proxy**: **trình duyệt gọi thẳng backend** (khác origin với site
Next). Các request này là **credentialed** (kèm cookie refresh + header Authorization). Hiện tại backend:

- **Chưa cấu hình CORS** → trình duyệt chặn mọi request cross-origin (kể cả preflight `OPTIONS`).
- `cookie.samesite="lax"`, `cookie.secure=false` (`resources/application.yml`) → cookie refresh
  **không** được gửi/nhận trong ngữ cảnh cross-site.

Không chỉnh 2 điểm này thì: đăng nhập có thể trả `accessToken` nhưng **trình duyệt vứt response** (thiếu
CORS), và **không lưu được cookie refresh** → mất phiên ngay khi reload.

## Cần thay đổi (2 phần)

### 1. Bật CORSMiddleware (FastAPI)

Thêm vào [`app/shop_web_adapter.py`](../../app/shop_web_adapter.py), trong `build_app`, **sau** khi đã
add `JwtMiddleware` để CORS là **lớp ngoài cùng** (xử lý preflight `OPTIONS` trước khi JWT middleware
chạy - middleware FastAPI theo LIFO: add sau = ngoài cùng = chạy trước).

```python
from starlette.middleware.cors import CORSMiddleware

class ShopWebAdapter(WebAdapter):
    def build_app(self, xime_app) -> FastAPI:
        fastapi_app = super().build_app(xime_app)
        register_exception_handlers(fastapi_app)

        # ... add JwtMiddleware như hiện tại ...

        # CORS: add SAU JwtMiddleware để là lớp ngoài cùng (xử lý preflight trước).
        # CORS must be the outermost layer so OPTIONS preflight is handled before JWT.
        config = xime_app.get(RuntimeConfig)  # hoặc cách lấy config đang dùng
        origins = config.get("cors.allow_origins", ["http://localhost:3000"])
        fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,          # PHẢI là danh sách origin CỤ THỂ
            allow_credentials=True,         # cho phép gửi cookie + Authorization
            allow_methods=["*"],
            allow_headers=["*"],
        )
        return fastapi_app
```

> ⚠️ **Khi `allow_credentials=True` thì `allow_origins` KHÔNG được là `"*"`.** Trình duyệt từ chối
> wildcard với request credentialed. Phải liệt kê origin cụ thể của frontend (dev + prod).

### 2. Cookie refresh phải gửi được cross-site

Sửa `resources/application.yml` (hoặc `application-local.yml`):

```yaml
cookie:
  secure: true        # bắt buộc khi samesite=none; cần chạy HTTPS
  samesite: "none"    # cross-site mới gửi được cookie
```

`set_refresh_cookie` trong [`app/security/cookies.py`](../../app/security/cookies.py) đã đọc 2 giá trị
này nên **không cần sửa code**, chỉ sửa cấu hình.

## Thêm khối cấu hình `cors` vào application.yml

```yaml
# CORS - origin của frontend Next được phép gọi thẳng (KHÔNG dùng "*" khi có credentials).
cors:
  allow_origins:
    - "http://localhost:3000"      # dev
    - "https://shop.scime.click"   # prod (đổi theo domain thật của frontend)
```

## Ràng buộc quan trọng (đọc kỹ)

- **`allow_credentials=True` + origin cụ thể** (không wildcard). Frontend fetch phải đặt
  `credentials: "include"`.
- **`samesite=none` bắt buộc đi kèm `secure=true`**, và `secure` yêu cầu **HTTPS**. Trên dev `http://`
  thuần, cookie `SameSite=None; Secure` sẽ bị trình duyệt bỏ. Lựa chọn cho dev:
  - Chạy backend qua HTTPS local (khuyến nghị, sát production), hoặc
  - Tạm để frontend + backend **same-site** khi dev (vd cùng `localhost` khác cổng vẫn là cross-origin
    nhưng same-site → có thể dùng `samesite=lax`), rồi bật `none` khi lên prod.
- **Path cookie refresh** giữ nguyên `/api/refresh-token` (đã path-scoped). Trình duyệt chỉ gửi cookie
  này tới đúng endpoint refresh - đúng thiết kế, không cần đổi.
- Nếu sau này phục vụ ảnh `/media` cho thẻ `<img>` cross-origin có dùng `crossorigin`, cân nhắc header
  CORS cho cả route media (thường ảnh thường không cần).

## Kiểm tra nhanh (preflight)

```bash
curl -i -X OPTIONS "http://localhost:8088/api/login" \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

Kỳ vọng response có: `Access-Control-Allow-Origin: http://localhost:3000`,
`Access-Control-Allow-Credentials: true`, và liệt kê method/headers cho phép.

## Liên quan

- Mô hình token + no-proxy: [`auth-jwt.md`](auth-jwt.md), và kế hoạch frontend
  `D:\code\Monolithic\shop\frontend\.claude\docs\ke-hoach\phan-1-core.md` (bước 1.11, 1.12).
