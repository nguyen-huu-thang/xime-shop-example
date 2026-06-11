# Hệ thống Error Code

> Nguồn: `src/Exception/AppException.php`, `ErrorCode.php`, `ErrorCodeProvider.php`.

## Cơ chế PHP

- `ErrorCode` — bảng hằng số, mỗi mã là `['code' => int, 'message' => string, 'httpStatus' => int]`.
- `ErrorCodeProvider` — tra cứu message/httpStatus/code theo error key.
- `AppException(errorKey, customMessage?, previous?)` — đọc message + httpStatus từ provider.
- `ExceptionSubscriber` (kernel.exception) — bắt exception → trả JSON.

```php
throw new AppException('E2021');                       // dùng message mặc định
throw new AppException('E10711', $jsonValidationErrors); // override message
```

## Thiết kế Python (giữ nguyên semantics)

### `exception/error_code.py`

Dùng `Enum` hoặc dict hằng. Đề xuất dataclass + dict để tra cứu nhanh:

```python
# exception/error_code.py
from dataclasses import dataclass

@dataclass(frozen=True)
class ErrorDef:
    code: int
    message: str
    http_status: int

ERROR_CODES: dict[str, ErrorDef] = {
    "S0000": ErrorDef(-1, "Bạn đã đăng nhập", 303),
    "E0000": ErrorDef(0, "Lỗi không xác định", 500),
    "E2021": ErrorDef(2021, "Vai trò người dùng không được phép thực hiện hành động này", 403),
    "E2025": ErrorDef(2025, "Cần đăng nhập để thực hiện hành động này", 401),
    # ... copy đầy đủ từ ErrorCode.php
}

def get_error(key: str) -> ErrorDef:
    return ERROR_CODES.get(key, ERROR_CODES["E0000"])
```

### `exception/app_exception.py`

```python
class AppException(Exception):
    def __init__(self, error_key: str, custom_message: str | None = None):
        self.error_key = error_key
        err = get_error(error_key)
        self.code = err.code
        self.http_status = err.http_status
        self.message = custom_message or err.message
        super().__init__(self.message)
```

### `exception/handler.py` — map AppException → JSON

Đăng ký exception handler trong web adapter (FastAPI `add_exception_handler`).
Đây là **điểm cần tự thiết kế** — `routing-layer.md` của framework ghi rõ "Exception → HTTP status
code mapping" là gap chưa có sẵn.

```python
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(
        status_code=exc.http_status,
        content={"errorKey": exc.error_key, "code": exc.code, "message": exc.message},
    )
```

Đăng ký trong `config/security.py` hoặc nơi build web adapter. Kiểm tra Xime cung cấp hook nào để
add exception handler vào FastAPI app (xem web adapter của framework).

## Dải mã (giữ nguyên từ PHP)

| Dải | Miền | Ví dụ |
|---|---|---|
| 0000–0999 | Lỗi chung (connection, auth, resource) | E0021 phiên hết hạn |
| 1000–1999 | User Service | E1004 tài khoản không tồn tại, E1005 sai mật khẩu |
| 2000–2999 | Auth/Authz | E2021 không được phép, E2025 cần đăng nhập, E2050 refresh token sai |
| 3000–3999 | Payment | (chưa dùng nhiều) |
| 4000–4999 | Notification | E4010 không gửi được email |
| 5000–5999 | Data/File | E5011 định dạng file không hỗ trợ |
| 10000–19999 | Web bán hàng | E10200 không tìm thấy SP, E10711 dữ liệu sai định dạng |
| 20000+ | Lưu trữ / khác | |

> **Copy nguyên văn** toàn bộ bảng từ `ErrorCode.php` (dòng 6–267) sang `error_code.py`. Đây là việc
> cơ học, làm trong Phase 1.
