# Lỗi và mã lỗi

## Định dạng lỗi

Mọi lỗi nghiệp vụ trả về body JSON thống nhất:

```json
{
  "errorKey": "E10200",
  "code": 404,
  "message": "Không tìm thấy sản phẩm",
  "details": null
}
```

| Trường | Ý nghĩa |
|---|---|
| `errorKey` | Mã lỗi nội bộ dạng `E` + số (ổn định, để client nhận diện) |
| `code` | HTTP status tương ứng (400, 401, 403, 404, 409, 413, 422, 500...) |
| `message` | Thông điệp tiếng Việt cho người dùng |
| `details` | Thông tin phụ (vd danh sách lỗi validation), có thể null |

## Cơ chế

- Tầng nghiệp vụ ném `AppException("Exxxx")`; một exception handler đăng ký trong `config/web.py`
  (`configure_exception_handlers`) map sang HTTP status + body trên.
- Lỗi validation của Pydantic/FastAPI được đồng nhất về cùng định dạng `{errorKey, code, message}`.
- **Không** trả 500 thô cho lỗi nghiệp vụ - luôn đi qua `AppException`.

## Một số mã thường gặp

| HTTP | Ý nghĩa | Ví dụ tình huống |
|---|---|---|
| 401 | Chưa đăng nhập / token không hợp lệ | gọi endpoint cần đăng nhập mà thiếu token |
| 403 | Không đủ quyền / không phải chủ sở hữu | xem đơn của người khác (IDOR đã chặn) |
| 404 | Không tìm thấy | sản phẩm/đơn không tồn tại hoặc đã xóa mềm |
| 409 | Xung đột | trùng dữ liệu duy nhất (vd username/email/coupon code) |
| 413 | Tải lên quá lớn | file upload vượt giới hạn dung lượng |
| 422 | Dữ liệu vào không hợp lệ | body sai ràng buộc Pydantic |

> Mã `errorKey` cụ thể được định nghĩa trong tầng `exception/`. Client nên dựa vào `errorKey` để xử lý
> theo tình huống thay vì so khớp `message` (vì message có thể đổi).

## Quy ước phía client

- Hiển thị `message` cho người dùng.
- Với `401`: thử refresh token một lần (qua `/api/refresh-token`), nếu vẫn lỗi thì đăng xuất.
- Với `403`: báo "không có quyền" thay vì cố thử lại.
