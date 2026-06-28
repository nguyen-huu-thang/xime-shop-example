# Shop Backend (Python/Xime)

Bản migrate **Shop Backend** từ PHP/Symfony sang Python, dùng framework **[Xime](https://github.com/nguyen-huu-thang/xime-framework)** với kiến trúc đa lớp.

> **Mục đích chính của dự án này là kiểm thử framework Xime trong thực tế** - xác minh các tính năng
> DI, routing, transaction, security, SQLAlchemy starter hoạt động đúng trên một ứng dụng backend
> thật quy mô vừa. Dự án đồng thời là **tài liệu tham khảo** (reference implementation) cho bất kỳ
> ai muốn học cách xây dựng ứng dụng Python với Xime theo kiến trúc đa lớp.

## Dự án gốc (PHP/Symfony)

Toàn bộ nghiệp vụ được sao chép 1-1 từ dự án backend gốc viết bằng **PHP/Symfony**:

➡️ **[github.com/nguyen-huu-thang/shop-backend](https://github.com/nguyen-huu-thang/shop-backend)**

Dự án Python này giữ nguyên kiến trúc đa lớp và logic nghiệp vụ của bản gốc, chỉ thay đổi
ngôn ngữ và framework. Bảng đối chiếu công nghệ giữa hai bản:

| Bản gốc (PHP) | Bản này (Python) |
|---|---|
| PHP 8.2+ / Symfony | Python 3.12+ / Xime framework |
| Doctrine ORM | SQLAlchemy (async) qua `xime.starters.sqlalchemy` |
| Symfony Validator | Pydantic |
| Symfony DI (autowire) | Xime DI (constructor injection, type-hint driven) |
| Lcobucci JWT | PyJWT qua `xime.starters.jwt` |
| EventListener (kernel.request) | Web middleware của Xime |
| nelmio_api_doc | OpenAPI/Swagger tích hợp sẵn FastAPI |
| MySQL hoặc PostgreSQL | PostgreSQL |

> Cùng tác giả; bản PHP được phát triển trước, bản Python là phiên bản viết lại để kiểm thử Xime.

## Xime framework — những gì được kiểm chứng qua dự án này

| Tính năng Xime | Được kiểm thử ở |
|---|---|
| Scan-based DI (không annotation) | Toàn bộ service, repository, controller |
| Class-based controller + decorator route | `controller/` — 18 controller |
| `from __future__ import annotations` bắt buộc trên Python 3.14 khi method tên trùng builtin | Tất cả controller có method `list` |
| `TransactionManager` từ `xime.core.transaction.manager` | Mọi service có thao tác ghi |
| `AsyncSessionFactory.current()` | `BaseRepository` |
| `xime.starters.sqlalchemy` starter | `config/database.py` |
| `xime.adapters.web.openapi.JwtBearer` | `config/web.py` |
| `TestApplication` + lifespan context trong test | `test/test_integration_db.py` |
| Security context (`identity`, `credentials`) | `security/current_user.py` |

## Yêu cầu

- Python 3.12+
- PostgreSQL 14+
- Framework Xime

## Cài đặt

```bash
# 1. Cài Xime framework
pip install xime

# 2. Cài dependencies dự án
pip install -e ".[dev]"

# 3. Sao chép file môi trường
cp .env.example .env
# Chỉnh sửa .env với thông tin DB và JWT thực tế
```

## Cấu hình

Tạo file `.env` dựa trên `.env.example`. Các biến bắt buộc:

| Biến | Mô tả |
|---|---|
| `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `JWT_SECRET_KEY` | Chuỗi bí mật JWT (tối thiểu 32 ký tự) |
| `UPLOAD_DIR` | Thư mục lưu file upload (mặc định: `public/data`) |

## Khởi tạo cơ sở dữ liệu

```bash
# Chạy migration (Alembic)
alembic upgrade head

# Seed dữ liệu khởi tạo (quyền + nhóm admin + tài khoản admin)
python -m app.seed
```

Tài khoản admin mặc định: `admin` / `Admin@123` — **đổi mật khẩu ngay sau khi seed**.

## Chạy ứng dụng

```bash
python app/main.py
```

Server chạy tại `http://localhost:8088` (hoặc theo cấu hình Xime).

Swagger UI: `http://localhost:8088/docs`

## Chạy tests

```bash
pytest test/
```

## Cấu trúc thư mục

```
app/
├── config/          # DI, web adapter, database config
├── controller/      # HTTP endpoints (class-based, Xime routing)
├── service/         # Business logic
├── repository/      # Data access (SQLAlchemy async)
├── entity/          # SQLAlchemy models
├── dto/             # Request/Response Pydantic models
│   ├── request/
│   └── response/
├── exception/       # AppException, error codes, handler
├── security/        # JWT middleware, current_user context
└── seed.py          # Dữ liệu khởi tạo
```

## Danh sách API chính

| Module | Prefix | Mô tả |
|---|---|---|
| Auth | `/api` | login, logout, refresh, change-password |
| Phân quyền | `/api/group`, `/api/permission`, ... | Nhóm, quyền, phân quyền |
| Catalog | `/api/categories`, `/api/products` | Danh mục, sản phẩm |
| Mua hàng | `/api/cart`, `/api/orders`, `/api/coupons` | Giỏ hàng, đơn hàng |
| Tương tác | `/api/reviews`, `/api/wishlist`, `/api/notifications` | Đánh giá, yêu thích |
| File | `/api/files` | Upload/quản lý file (stream tải xuống qua `/media/{key}`, hỗ trợ HTTP Range) |
| Tìm kiếm | `/api/search` | Tìm kiếm sản phẩm |
| Dashboard | `/api/dashboard/stats` | Thống kê quản trị (doanh thu, đơn, bán chạy, tồn kho thấp) |

> **Xác thực (cập nhật):** `POST /api/login` trả `accessToken` trong body (client lưu RAM) và đặt
> refresh token vào **httpOnly cookie** path-scoped `/api/refresh-token`. `POST /api/refresh-token`
> đọc refresh từ cookie, cấp access mới và **xoay** refresh token (đặt lại cookie). JS không đọc được
> refresh token; cookie không gửi kèm các API khác.
