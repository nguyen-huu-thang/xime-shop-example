# Quy tắc Code — Kiến trúc Đa lớp + Xime DI

> Bối cảnh: [`../docs/kien-truc-da-lop.md`](../docs/kien-truc-da-lop.md).

## 1. Không annotation cho DI

Không dùng `@service`, `@repository`, `@inject`... Loại component suy từ **thư mục**.
Các package được scan khai báo trong `config/dependency.py`:

```python
dependency.scan("controller", "service", "repository", "security")
```

## 2. Constructor injection, type hint bắt buộc

```python
class CategoryService:
    def __init__(
        self,
        transaction: TransactionManager,
        category_repository: CategoryRepository,
        product_service: ProductService,
    ):
        self._transaction = transaction
        self._category_repository = category_repository
        self._product_service = product_service
```

- Mọi tham số `__init__` **phải có type hint** → thiếu hint thì param đó không được inject (xem rule gốc của framework).
- Phụ thuộc **class cụ thể**, không qua Protocol (khác Hexagonal). Không cần `dependency.bind()` cho các phụ thuộc nội bộ.

## 3. Tầng phụ thuộc đúng hướng

```
controller → service → repository → entity
controller → service (khác)        # service gọi service khác OK (như PHP)
```

- **Controller** chỉ gọi service (+ authorization service). Không truy vấn DB trực tiếp.
- **Service** chứa business logic, mở transaction, gọi repository / service khác.
- **Repository** chỉ truy vấn DB, **không** chứa business logic, **không** mở transaction.
- **Entity/DTO/Exception** thuần dữ liệu, không phụ thuộc tầng trên.

## 4. Async toàn bộ

SQLAlchemy async + FastAPI async. Mọi method I/O là `async def`, gọi bằng `await`.

## 5. Đặt tên

| Loại | Quy ước | Ví dụ |
|---|---|---|
| File | snake_case | `category_service.py` |
| Class | PascalCase, giữ tên PHP | `CategoryService` |
| Method | snake_case (PHP camelCase → snake) | `getAllCategories` → `get_all_categories` |
| Biến private | `_` prefix | `self._repo` |

## 6. Transaction tường minh

Service mở transaction, **không** dùng `@transactional`:

```python
async def create_category(self, data) -> Category:
    async with self._transaction():
        category = Category(name=data.name, ...)
        await self._category_repository.save(category)
        return category
```

Đọc thuần (không ghi) thì không cần transaction. Xem [`transaction.md`](transaction.md).

## 7. Controller — class-based, decorator route

```python
from xime.adapters.web.routing import get, post, put, delete

class CategoryController:
    prefix = "/api/categories"
    tags = ["categories"]

    def __init__(self, category_service: CategoryService, authz: AuthorizationService):
        self._service = category_service
        self._authz = authz

    @get("")
    async def list(self) -> list[CategoryResponse]:
        items = await self._service.get_all_categories()
        return [CategoryResponse.model_validate(c) for c in items]

    @post("", status_code=201)
    async def create(self, body: CategoryCreateRequest) -> CategoryResponse:
        await self._authz.require(current_user(), "create_category")
        category = await self._service.create_category(body)
        return CategoryResponse.model_validate(category)
```

- `prefix`/`tags` là class attribute (không decorator class).
- Body request → tham số kiểu Pydantic; FastAPI tự parse + validate.
- Path param → tham số trùng tên trong path: `@get("/{id}")` → `async def detail(self, id: int)`.
- Phải khai báo `configure_controllers("controller")` trong `config/routing.py`.

## 8. Xử lý lỗi

- Dùng `AppException("Exxxx")` cho lỗi nghiệp vụ — handler tự map sang HTTP status.
- **Không** `try/except` rỗng. Không nuốt lỗi.
- Không trả lỗi 500 thô cho lỗi nghiệp vụ — luôn qua `AppException`.

## 9. Comment

Tiếng Anh trên, tiếng Việt dưới (theo quy ước cá nhân):

```python
# Calculate total amount including shipping
# Tính tổng tiền bao gồm phí vận chuyển
total = subtotal + shipping_fee
```

## 10. Giữ sát bản gốc PHP

Khi nghi ngờ, **đối chiếu file PHP tương ứng**. Mục tiêu là copy nghiệp vụ, không "cải tiến" tùy tiện.
Nếu thấy cách làm PHP có vấn đề → ghi chú lại, hỏi người dùng, đừng tự sửa logic.
