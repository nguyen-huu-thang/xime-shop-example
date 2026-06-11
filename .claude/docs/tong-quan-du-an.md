# Tổng quan dự án

## Mục tiêu

Migrate (copy) dự án **shop backend** từ **PHP/Symfony** sang **Python**, dùng framework **Xime**
do người dùng tự thiết kế. Giữ nguyên nghiệp vụ và cấu trúc đa lớp của dự án gốc.

## Mục đích & phạm vi (quan trọng)

Đây là **bản tham chiếu / kiểm thử cho framework Xime**, **KHÔNG** phải sản phẩm thương mại. Dùng để
chứng minh framework chạy được ứng dụng thật và làm tài liệu mẫu cho người khác tham khảo.

→ **Không** migrate dữ liệu cũ; được tự do chọn giải pháp sạch/đơn giản; ưu tiên làm nổi bật cách dùng
framework. Khi code PHP và schema mâu thuẫn, chốt phương án hợp lý và ghi vào
[`quyet-dinh-thiet-ke.md`](quyet-dinh-thiet-ke.md) — **không cần hỏi lại**.

## Nguồn PHP gốc

- **Root**: `D:\code\PHP\shop-backend\`
- **Source**: `src/`
  - `Controller/Api/` — 18 controller REST
  - `Service/` — business logic
  - `Repository/` — data access (Doctrine `ServiceEntityRepository`)
  - `Entity/` — 25 Doctrine entity
  - `Dto/` — output DTO (khởi tạo từ entity)
  - `Validators/` — validate input (Symfony Validator)
  - `Exception/` — `AppException`, `ErrorCode`, `ErrorCodeProvider`
  - `EventListener/` — `JwtAuthenticatorListener` (xác thực JWT toàn cục)
  - `Command/` — `SetupInitialCommand` (seed quyền/dữ liệu ban đầu)
- **Config**: `config/services.yaml`, `config/packages/*.yaml`
- **Tài liệu nghiệp vụ**: `giải thích cơ sở dữ liệu.txt` (rất quan trọng — giải thích schema + nghiệp vụ)

## Stack PHP → Python

| PHP / Symfony | Python / Xime |
|---|---|
| Symfony Framework | Xime framework |
| Doctrine ORM | SQLAlchemy (async) qua `xime.starters.sqlalchemy` |
| Lcobucci JWT | PyJWT qua `xime.starters.jwt` |
| Symfony Validator | Pydantic |
| Symfony DI (autowire) | Xime DI (constructor injection, type-hint driven) |
| `EntityManagerInterface` | `AsyncSession` + `TransactionManager` |
| EventListener (kernel.request) | Web middleware của Xime |
| `nelmio_api_doc` | OpenAPI/Swagger tích hợp sẵn FastAPI |

## Phạm vi tính năng (theo controller PHP)

| Module | Controller PHP | Mô tả |
|---|---|---|
| Auth | `SecurityController` | login, logout, refresh token, đổi/xác thực mật khẩu |
| User | `UserController` | CRUD người dùng |
| Group | `GroupController`, `GroupMemberController`, `GroupPermissionController` | nhóm + thành viên + quyền nhóm |
| Permission | `PermissionsController`, `UserPermissionController` | quyền hệ thống + quyền cá nhân |
| Category | `CategoryController` | danh mục phân cấp cha-con |
| Product | `ProductController` | sản phẩm + thuộc tính + tùy chọn |
| Cart | `CartController` | giỏ hàng |
| Order | `OrderController`, `OrderDetailController` | đơn hàng |
| Coupon | `CouponController` | mã giảm giá |
| Review | `ReviewController` | đánh giá |
| Wishlist | `WishlistController` | danh sách yêu thích |
| File | `FileController` | upload file |
| Notification | `NotificationController` | thông báo |
| Search | `SearchController` | tìm kiếm sản phẩm |

> Chi tiết entity/schema xem [`domain-model.md`](domain-model.md).
