# Issue #2 — Thiếu hook public để đăng ký exception handler / middleware tùy chỉnh

- **Mức độ:** Trung bình (có workaround sạch)
- **Phase phát hiện:** Phase 1 (xây dựng exception handling)
- **Thành phần:** `xime.adapters.web.WebAdapter`

## Hiện tượng

`WebAdapter` tự thêm sẵn `RequestContextMiddleware` và `JwtAuthMiddleware`, nhưng **không** cung cấp
API public để:
1. Đăng ký FastAPI exception handler toàn cục (vd map `AppException` → JSON).
2. Thêm middleware tùy chỉnh của ứng dụng.

Tài liệu `routing-layer.md` của chính framework cũng ghi nhận "Exception → HTTP status code mapping"
là một gap chưa có sẵn.

## Ảnh hưởng

Ứng dụng cần định dạng lỗi đồng nhất (như shop: `{errorKey, code, message}`) phải tự can thiệp vào
FastAPI app. Nếu không có cách, phải lặp `try/except` ở mọi controller (như data service đang làm —
mỗi handler bắt exception rồi raise `HTTPException`), gây trùng lặp lớn.

## Workaround đang dùng (sạch, hiệu quả)

Vì `WebAdapter.start()` gọi `self.build_app(app)`, ta **subclass** và override `build_app`:

```python
# app/shop_web_adapter.py
class ShopWebAdapter(WebAdapter):
    def build_app(self, xime_app) -> FastAPI:
        fastapi_app = super().build_app(xime_app)
        register_exception_handlers(fastapi_app)   # app.add_exception_handler(...)
        return fastapi_app
```

`main.py` dùng `app.use(ShopWebAdapter())`. Áp dụng cho cả `run()` lẫn test (vì test cũng gọi
`build_app`). Đã kiểm chứng: `AppException("E2021")` → HTTP 403 JSON `{errorKey,code,message}`.

## Đề xuất cho framework

1. Thêm hook khi build app, ví dụ:
   ```python
   configure_web(on_app_built=lambda app: register_exception_handlers(app))
   # hoặc
   WebAdapter(exception_handlers={AppException: handler}, middlewares=[...])
   ```
2. Hoặc cung cấp `configure_exception_handlers({ExcType: handler})` tương tự `configure_controllers()`,
   `configure_openapi()` — nhất quán với pattern `configure_*()` hiện có.

Workaround subclass hoạt động tốt nên **không chặn tiến độ**, chỉ là gợi ý cải thiện DX.
