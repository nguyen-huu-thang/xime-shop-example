# Kiến trúc

Shop Backend dùng **kiến trúc đa lớp (layered)** trên nền XIME Framework. Đây là lựa chọn có chủ đích
để giữ sát bản gốc PHP/Symfony, **KHÔNG** dùng Hexagonal/Clean/Onion như XIME khuyến nghị mặc định.

## Các tầng và chiều phụ thuộc

```text
controller  →  service  →  repository  →  entity
               ↘ service (khác)
```

| Tầng | Trách nhiệm | Không được làm |
|---|---|---|
| **controller** | Nhận HTTP, parse/validate input (Pydantic), gọi service, trả DTO | Truy vấn DB trực tiếp, chứa business logic |
| **service** | Business logic, mở transaction, gọi repository / service khác | Biết về HTTP (request/response) |
| **repository** | Truy vấn DB (SQLAlchemy async) | Chứa business logic, mở transaction |
| **entity / dto / exception** | Dữ liệu thuần | Phụ thuộc tầng trên |

Service được phép gọi service khác (giống bản PHP). Phụ thuộc luôn đi **một chiều** xuống dưới.

## Cây thư mục

```text
app/
├── config/         # DI binding, web (CORS/middleware/exception), database, routing, scheduler
├── controller/     # HTTP endpoint - class-based, decorator route của XIME
├── service/        # Business logic, mở transaction
├── repository/     # Truy vấn DB (CrudRepository[T] của XIME)
├── entity/         # SQLAlchemy model (bảng)
├── dto/
│   ├── request/    # Pydantic input (validate + parse body)
│   └── response/   # Pydantic output
├── exception/      # AppException + bảng error code + handler
├── security/       # JwtMiddleware (pure-ASGI), ngữ cảnh current_user
├── cache/          # cache catalog + PermissionRegistry
├── job/            # job theo lịch (vd dựng lại co-occurrence)
├── seed.py         # seed quyền/nhóm/admin
└── seed_catalog.py # seed dữ liệu catalog demo
migrations/         # Alembic
resources/          # application.yml (+ application-local.yml, application-production.yml)
test/               # pytest
```

## Dependency Injection (XIME)

XIME tự inject phụ thuộc theo **type hint** của constructor - không annotation, không decorator, không
wire thủ công. Loại component được suy ra từ **thư mục** (controller/service/repository/security được
khai báo scan trong `config/dependency.py`).

```python
class CategoryService:
    def __init__(
        self,
        transaction: TransactionManager,
        category_repository: CategoryRepository,
        product_service: ProductService,
    ) -> None:
        self._transaction = transaction
        self._category_repository = category_repository
        self._product_service = product_service
```

- Mọi tham số `__init__` phải có type hint, nếu không sẽ không được inject.
- Phụ thuộc **class cụ thể** (không qua Protocol như Hexagonal).

## Controller class-based

```python
from xime.adapters.web.routing import get, post

class CategoryController:
    prefix = "/api/categories"
    tags = ["categories"]

    def __init__(self, category_service: CategoryService, authz: AuthorizationService) -> None:
        self._service = category_service
        self._authz = authz

    @get("")
    async def list(self) -> list[CategoryResponse]:
        items = await self._service.get_all_categories()
        return [CategoryResponse.model_validate(c) for c in items]
```

- `prefix` / `tags` là class attribute.
- Body request -> tham số kiểu Pydantic; FastAPI tự parse + validate.
- Path param -> tham số trùng tên: `@get("/{id}")` -> `async def detail(self, id: int)`.

## Transaction tường minh

XIME **không** dùng `@transactional`/AOP. Service mở transaction bằng async context manager:

```python
async def create_order(self, data) -> Order:
    async with self._transaction():
        order = Order(...)
        await self._order_repo.save(order)
        for line in data.items:
            await self._order_detail_repo.save(OrderDetail(order_id=order.id, ...))
        return order
    # thoát block không lỗi -> COMMIT; có exception -> ROLLBACK
```

- Mở transaction ở **service**, không ở controller/repository.
- Ghi nhiều bảng trong một nghiệp vụ -> gói chung một transaction (atomic).
- Đọc thuần không cần transaction.

> Lưu ý starter SQLAlchemy của XIME: repository lấy session qua `AsyncSessionFactory.current()`, chỉ
> có hiệu lực **bên trong** một transaction đang mở. Repository chỉ `add`/`flush`/`delete`;
> commit/rollback do `async with self._transaction()` lo.

## Repository

```python
from sqlalchemy import select
from xime.starters.sqlalchemy import CrudRepository
from app.entity.category import Category

class CategoryRepository(CrudRepository[Category]):
    model = Category

    async def find_by_parent_id(self, parent_id: int) -> list[Category]:
        result = await self.session.execute(
            select(Category).where(Category.parent_id == parent_id)
        )
        return list(result.scalars().all())
```

`CrudRepository[T]` (của XIME) cung cấp sẵn `find`, `find_all`, `save`, `delete`, `count`, `exists`...
Mỗi repository ứng với một entity và chỉ chứa truy vấn.

## Tầng web (CORS / middleware / exception)

Dự án dùng API của XIME để cấu hình web layer trong `config/web.py`:

- `configure_cors(...)` - origin frontend được phép gọi.
- `configure_middleware(JwtMiddleware, ...)` - giải JWT, gắn ngữ cảnh người dùng (pure-ASGI).
- `configure_exception_handlers({...})` - map `AppException` sang HTTP + `{errorKey, code, message}`.

`main.py` chỉ còn `WebAdapter()` (không tự viết adapter). Thứ tự middleware: CORS đứng trước
`JwtMiddleware` để request preflight OPTIONS không bị chặn bởi xác thực.

## Đọc tiếp

- [Mô hình dữ liệu](mo-hinh-du-lieu.md)
- [Phân quyền](phan-quyen.md)
- [Lỗi và mã lỗi](loi-va-ma-loi.md)
