# Shop Backend (Python / Xime)

> Backend thương mại điện tử (bán hàng) xây dựng bằng **Python** trên framework
> **[Xime](https://github.com/nguyen-huu-thang/xime-framework)**, theo **kiến trúc đa lớp (layered)**.
> Đây là bản migrate 1-1 từ một backend gốc viết bằng **PHP/Symfony**.

Dự án này có hai mục đích:

1. **Kiểm thử Xime framework trong thực tế** - xác minh DI, routing, transaction, security, SQLAlchemy
   starter hoạt động đúng trên một backend thật quy mô vừa.
2. **Bản tham khảo (reference implementation)** cho ai muốn xây dựng ứng dụng Python với Xime theo
   kiến trúc đa lớp (KHÔNG dùng Hexagonal/Clean như Xime khuyến nghị mặc định).

```text
Trình duyệt / Frontend Next.js
        │  HTTP (JSON), JWT
        ▼
   Shop Backend (FastAPI qua Xime WebAdapter)
   controller → service → repository → entity
        │
        ▼
   PostgreSQL  +  Local Disk (ảnh, file)
```

---

## Hệ sinh thái dự án

| Thành phần | Repo |
|---|---|
| **Backend (repo này)** | [nguyen-huu-thang/xime-shop-example](https://github.com/nguyen-huu-thang/xime-shop-example) |
| **Frontend (Next.js)** | [nguyen-huu-thang/shop-frontend-v2](https://github.com/nguyen-huu-thang/shop-frontend-v2) |
| Bản gốc PHP/Symfony (backend) | [nguyen-huu-thang/shop-backend](https://github.com/nguyen-huu-thang/shop-backend) |
| Bản gốc React (frontend) | [nguyen-huu-thang/shop-frontend](https://github.com/nguyen-huu-thang/shop-frontend) |
| XIME Framework | [nguyen-huu-thang/xime-framework](https://github.com/nguyen-huu-thang/xime-framework) |

> **Frontend** dùng Next.js + React, gọi thẳng các API của backend này. Mô hình giao tiếp, danh sách
> endpoint và cách tích hợp xem ở repo frontend bên trên và tại [`docs/api.md`](docs/api.md).

---

## Tính năng

- **Xác thực JWT** - access token trả body (client lưu RAM), refresh token đặt trong **httpOnly cookie**
  path-scoped `/api/refresh-token`, có xoay token (rotation).
- **Catalog** - danh mục dạng cây, sản phẩm + biến thể (thuộc tính / option / SKU), ảnh sản phẩm
  (trả kèm `imageUrl`, stream qua `/media/{key}` hỗ trợ HTTP Range), tìm kiếm.
- **Giỏ hàng - Yêu thích - Đánh giá** - thao tác self-service theo người dùng đăng nhập.
- **Thanh toán (checkout)** - sổ địa chỉ, mã giảm giá nâng cấp (theo %/số tiền, trần giảm, đơn tối
  thiểu, phạm vi tiền hàng/phí ship, giới hạn lượt, mỗi người 1 lần), xem trước tổng tiền, tạo đơn
  theo địa chỉ + coupon + phương thức (COD / online giả lập), cổng thanh toán mô phỏng.
- **Thông báo in-app** - hộp thư theo người dùng, đếm chưa đọc, đánh dấu đã đọc, broadcast cho admin.
- **Email** - email giao dịch (xác nhận đơn, thanh toán) + email bảo mật (xác minh email, quên/đặt
  lại mật khẩu, OTP). Tự TẮT khi chưa cấu hình SMTP nên không chặn luồng chính.
- **Gợi ý / cá nhân hóa (không AI)** - "đã xem gần đây", "thịnh hành", "gợi ý cho bạn", "hay mua
  cùng"; dựa trên kho sự kiện có trọng số + affinity danh mục + co-occurrence đồng mua.
- **Phân quyền RBAC + ACL** - deny-overrides, superadmin bypass, scope theo nhánh danh mục, kiểm tra
  quyền sở hữu (chống IDOR); thao tác trên dữ liệu của chính mình chỉ cần đăng nhập.
- **Dashboard** thống kê quản trị, **cache** catalog, tối ưu **N+1** cho sản phẩm/biến thể.

Chi tiết từng mảng xem trong [Tài liệu](#tài-liệu).

---

## Công nghệ

| Hạng mục | Lựa chọn |
|---|---|
| Ngôn ngữ | Python 3.12+ (phát triển trên 3.14) |
| Framework | XIME (DI, routing, transaction, starters) trên nền FastAPI |
| ORM | SQLAlchemy 2 (async) qua `xime.starters.sqlalchemy` |
| CSDL | PostgreSQL |
| Validation | Pydantic 2 |
| Migration | Alembic |
| Mật khẩu | passlib + bcrypt |
| Email | aiosmtplib qua `xime.starters.mail` (tùy chọn) |

Đối chiếu với bản gốc PHP:

| Bản gốc (PHP) | Bản này (Python) |
|---|---|
| PHP 8.2+ / Symfony | Python 3.12+ / XIME |
| Doctrine ORM | SQLAlchemy async |
| Symfony Validator | Pydantic |
| Symfony DI (autowire) | XIME DI (constructor injection theo type hint) |
| Lcobucci JWT | PyJWT qua `xime.starters.jwt` |
| EventListener (kernel.request) | Web middleware của XIME |
| nelmio_api_doc | OpenAPI/Swagger sẵn trong FastAPI |

---

## Bắt đầu nhanh

### Yêu cầu

- Python 3.12+
- PostgreSQL 14+
- XIME Framework 0.6.2+ (cài từ PyPI)

### Cài đặt

```bash
# 1. Cài XIME framework (từ PyPI, phiên bản mới nhất 0.6.2)
pip install xime

# 2. Cài phụ thuộc dự án
pip install -e ".[dev]"
```

### Cấu hình

Cấu hình runtime nằm trong [`resources/application.yml`](resources/application.yml) (server, database,
jwt, cookie, cors, storage, mail). **Không commit bí mật thật** - ghi đè cục bộ qua
`resources/application-local.yml` (đã gitignore). Các khối quan trọng:

```yaml
database:
  url: "postgresql+asyncpg://user:pass@localhost:5432/shop"
jwt:
  secret: "đổi-thành-chuỗi-ngẫu-nhiên-tối-thiểu-32-ký-tự"
storage:
  local:
    root: "public/data"     # nơi lưu ảnh/file trên đĩa
```

### Khởi tạo CSDL

```bash
alembic upgrade head          # tạo bảng
python -m app.seed            # quyền + nhóm admin + tài khoản admin (admin / Admin@123)
python -m app.seed_catalog    # (tùy chọn) nạp dữ liệu catalog demo
```

> Đổi mật khẩu admin ngay sau khi seed.

### Chạy

```bash
python app/main.py
```

- API: `http://localhost:8088`
- Swagger UI: `http://localhost:8088/docs`

### Kiểm thử

```bash
pytest
```

---

## Kiến trúc (tóm tắt)

Dự án theo **kiến trúc đa lớp**, phụ thuộc đi một chiều:

```text
controller → service → repository → entity
            ↘ service (khác)
```

```text
app/
├── config/        # DI binding, web (CORS/middleware/exception), database, routing
├── controller/    # HTTP endpoint (class-based, decorator route của XIME)
├── service/       # Business logic, mở transaction, gọi repository / service khác
├── repository/    # Truy vấn DB (SQLAlchemy async, CrudRepository)
├── entity/        # SQLAlchemy model
├── dto/           # request/ (Pydantic input) + response/ (output)
├── exception/     # AppException + error code + handler
├── security/      # JWT middleware, ngữ cảnh current_user
├── cache/         # cache catalog + registry quyền
├── seed.py        # seed quyền/nhóm/admin
└── seed_catalog.py# seed dữ liệu catalog demo
```

XIME tự inject phụ thuộc theo **type hint** của constructor - không annotation, không wire thủ công.
Transaction được mở **tường minh** ở tầng service. Chi tiết: [`docs/kien-truc.md`](docs/kien-truc.md).

---

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [Tổng quan](docs/tong-quan.md) | Backend làm gì, ranh giới, vị trí trong hệ sinh thái |
| [Kiến trúc](docs/kien-truc.md) | Kiến trúc đa lớp, XIME DI, transaction, cây thư mục |
| [Mô hình dữ liệu](docs/mo-hinh-du-lieu.md) | Các bảng chính + quan hệ (user, product, variant, order...) |
| [Phân quyền](docs/phan-quyen.md) | RBAC + ACL, deny-overrides, scope danh mục, ownership |
| [API](docs/api.md) | Bản đồ REST endpoint theo nhóm + quy ước request/response |
| [Tính năng](docs/tinh-nang.md) | Checkout/thanh toán, thông báo, email, gợi ý cá nhân hóa |
| [Lỗi và mã lỗi](docs/loi-va-ma-loi.md) | Định dạng lỗi `{errorKey, code, message}` |

---

## Trạng thái dự án

Đã hoàn thiện migrate và bổ sung đầy đủ nghiệp vụ (catalog, mua hàng, thanh toán, thông báo, email,
gợi ý, phân quyền nâng cấp). Toàn bộ kiểm thử tự động đang xanh. Đây là **bản tham khảo phục vụ học
tập** cho XIME Framework.

## Giấy phép

MIT
