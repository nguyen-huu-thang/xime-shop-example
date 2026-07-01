# Tổng quan

## Shop Backend là gì?

Shop Backend là phần máy chủ của một ứng dụng **thương mại điện tử (bán hàng)**: catalog sản phẩm,
giỏ hàng, đặt hàng, thanh toán, đánh giá, thông báo, email và gợi ý cá nhân hóa.

Nó được viết bằng **Python** trên framework **XIME**, theo **kiến trúc đa lớp (layered)**, và là bản
viết lại 1-1 từ một backend gốc bằng **PHP/Symfony**. Mục tiêu kép:

- **Kiểm thử XIME framework** trong một ứng dụng thật quy mô vừa.
- Làm **bản tham khảo** cách dựng ứng dụng Python với XIME theo kiến trúc đa lớp.

```text
Frontend (Next.js)
     │  gọi REST API (JSON) + JWT
     ▼
Shop Backend  ─ catalog, mua hàng, thanh toán, thông báo, gợi ý, phân quyền
     │
     ▼
PostgreSQL  +  Local Disk (ảnh/file)
```

## Vị trí trong hệ sinh thái

| Thành phần | Vai trò |
|---|---|
| [Frontend (shop-frontend-v2)](https://github.com/nguyen-huu-thang/shop-frontend-v2) | Giao diện Next.js, gọi thẳng API backend này |
| **Shop Backend (repo này)** | Toàn bộ nghiệp vụ + dữ liệu |
| [Bản gốc PHP/Symfony](https://github.com/nguyen-huu-thang/shop-backend) | Nguồn nghiệp vụ được sao chép |
| [XIME Framework](https://github.com/nguyen-huu-thang/xime-framework) | Nền tảng DI/routing/transaction/starters |

Backend tự chứa toàn bộ nghiệp vụ; frontend chỉ là tầng trình bày. Hai bên triển khai độc lập
(single-tenant: một cửa hàng một deploy).

## Triết lý thiết kế

| Câu hỏi | Trả lời |
|---|---|
| Kiến trúc nào? | Đa lớp (controller → service → repository → entity), KHÔNG Hexagonal |
| Vì sao không Hexagonal? | Giữ sát bản gốc PHP/Symfony để dễ đối chiếu; đơn giản, dễ bảo trì |
| DI ra sao? | XIME tự inject theo type hint constructor, suy loại component từ thư mục |
| Transaction? | Mở tường minh ở tầng service (`async with self._transaction()`) |
| Xác thực? | JWT: access token ở RAM client, refresh token httpOnly cookie path-scoped |
| Lỗi nghiệp vụ? | `AppException("Exxxx")` -> handler map sang HTTP + `{errorKey, code, message}` |

## Phạm vi nghiệp vụ

- **Catalog**: danh mục (cây), sản phẩm + biến thể (thuộc tính/option/SKU), ảnh, tìm kiếm.
- **Mua hàng**: giỏ hàng, yêu thích, đánh giá (chờ duyệt), đặt hàng.
- **Thanh toán**: sổ địa chỉ, mã giảm giá, xem trước tổng tiền, COD / online giả lập.
- **Sau bán**: thông báo in-app, email giao dịch, đổi trạng thái giao hàng.
- **Cá nhân hóa**: gợi ý theo hành vi (không AI, chấm điểm theo luật).
- **Quản trị**: phân quyền RBAC + ACL, dashboard thống kê.

## Shop Backend KHÔNG làm gì

- Không render giao diện - đó là việc của frontend.
- Không là cổng thanh toán thật - phần thanh toán online là **mô phỏng** phục vụ demo.
- Không gửi email khi chưa cấu hình SMTP - email tự tắt, không chặn nghiệp vụ chính.
- Không dùng AI cho gợi ý - chỉ chấm điểm theo luật (sự kiện có trọng số + affinity + co-occurrence).

## Đọc tiếp

- [Kiến trúc](kien-truc.md) - cách tổ chức tầng, DI, transaction.
- [Mô hình dữ liệu](mo-hinh-du-lieu.md) - các bảng và quan hệ.
- [API](api.md) - bản đồ endpoint.
