# Kiến trúc Đa lớp (Layered) — Quyết định cốt lõi của dự án

## Tóm tắt

Dự án PHP gốc theo **kiến trúc đa lớp (layered/N-tier)**:

```
Controller → Service → Repository → Entity
```

Dự án Python này **giữ nguyên kiến trúc đa lớp đó**, **KHÔNG** chuyển sang Hexagonal/Clean/Onion
mà framework Xime khuyến nghị.

## Tại sao không theo Hexagonal như Xime khuyến nghị?

Xime **khuyến khích** (chứ không **bắt buộc**) Hexagonal — xem `app-entry-point.md` của framework:
"Framework **không yêu cầu** cấu trúc thư mục cụ thể bên trong `./app`. Người lập trình tự do tổ chức."

Lý do dự án này chọn đa lớp:

1. **Trung thành với bản gốc** — mục tiêu là *copy* dự án PHP, không phải tái thiết kế. Giữ đa lớp giúp map 1-1, dễ đối chiếu, giảm sai sót.
2. **Đơn giản, dễ bảo trì** — dự án shop CRUD-nặng, không có domain logic phức tạp cần tách `port/inbound`, `port/outbound`, `usecase`, `mapper`.
3. **Service phụ thuộc trực tiếp Repository** — giống PHP (`CategoryService` nhận thẳng `CategoryRepository`), không cần lớp Protocol trung gian.

## So sánh với Hexagonal của Xime

| | Hexagonal (Xime khuyến nghị) | Đa lớp (dự án này) |
|---|---|---|
| Tầng API | `api/rest/external/` | `controller/` |
| Business | `application/usecase/` + `service/` | `service/` (gộp 1 tầng) |
| Interface | `port/inbound`, `port/outbound` (Protocol) | **không có** — phụ thuộc class cụ thể |
| Data access | `infrastructure/persistence/repository/` | `repository/` |
| Domain | `domain/` (entity, VO) | `entity/` |
| Mapper | `application/mapper/` | DTO tự map (xem `dto/`) |

## Vẫn tuân thủ các nguyên tắc DI của Xime

Đa lớp **không** có nghĩa là phá vỡ DI của Xime. Vẫn giữ:

- ✅ **Không annotation** — không `@service`, `@repository`. Loại component suy ra từ **thư mục**.
- ✅ **Constructor injection** — mọi dependency qua tham số `__init__` có type hint.
- ✅ **Type hint driven** — framework đọc type hint để build dependency graph.
- ✅ **Directory driven** — `service/`, `repository/`, `controller/` được khai báo trong `config/dependency.py` để scan.
- ✅ **Transaction tường minh** — `async with self.transaction():` (xem [`../rules/transaction.md`](../rules/transaction.md)).
- ✅ **Fail fast** — thiếu dependency/type hint → startup thất bại.

### Khác biệt chính so với Hexagonal: bỏ lớp Protocol

Trong Hexagonal, service phụ thuộc `UserRepository` (Protocol), bind sang `SqlUserRepository`.

Ở đây service phụ thuộc **trực tiếp** class cụ thể:

```python
# service/category_service.py
class CategoryService:
    def __init__(
        self,
        transaction: TransactionManager,
        category_repository: CategoryRepository,   # class cụ thể, KHÔNG phải Protocol
        product_service: ProductService,
    ):
        ...
```

→ **Không cần** `dependency.bind({...})` cho repository. Xime tự resolve class cụ thể qua constructor injection.

> **Khi nào vẫn dùng Protocol + bind?** Chỉ khi thật sự cần thay implementation theo môi trường
> (ví dụ `FileStorage` local vs S3). Mặc định: phụ thuộc trực tiếp cho đơn giản.

## Các tầng và trách nhiệm

| Tầng | Thư mục | Trách nhiệm | Được Xime scan? |
|---|---|---|---|
| **Controller** | `controller/` | Nhận HTTP request, gọi service, trả response. Kiểm tra phân quyền. | Có (qua `configure_controllers`) + DI |
| **Service** | `service/` | Business logic, điều phối repository, quản lý transaction. | Có |
| **Repository** | `repository/` | Truy vấn DB qua SQLAlchemy. | Có |
| **Entity** | `entity/` | SQLAlchemy ORM model. | **Không** (excluded) |
| **DTO** | `dto/` | Pydantic request/response model. | **Không** (excluded) |
| **Validator** | `validator/` | Validate input phức tạp (nếu Pydantic chưa đủ). | Có (nếu cần inject) |
| **Exception** | `exception/` | `AppException`, error code. | **Không** (excluded) |
| **Security** | `security/` | JWT middleware, context người dùng hiện tại. | Có |
| **Common** | `common/` | Tiện ích dùng chung. | Tùy (util thường excluded) |
| **Config** | `config/` | `dependency.py`, `routing.py`, `security.py`. | — |

> Xime mặc định **loại trừ** khỏi DI scan các package: `domain`, `dto`, `entity`, `vo`,
> `constant`, `exception`. Đó là lý do `entity/`, `dto/`, `exception/` không bị scan.

## Luồng một request điển hình

```
HTTP Request
   ↓
[Security Middleware]  → giải mã JWT, set user hiện tại vào context
   ↓
Controller.method()    → kiểm tra phân quyền (AuthorizationService)
   ↓                   → parse request DTO (Pydantic)
Service.method()       → async with transaction(): business logic
   ↓
Repository.method()    → truy vấn SQLAlchemy
   ↓
Entity                 → ORM model
   ↑
DTO response (Pydantic) ← Controller map entity → response DTO
   ↓
JSON Response
```

> Cây thư mục đầy đủ: [`cay-thu-muc.md`](cay-thu-muc.md).
