# DTO & Validation (Pydantic)

> Thay `App\Dto\*` (output) và `App\Validators\*` (Symfony Validator, input).

## Hai loại DTO

### Request DTO — input (`dto/request/`)

Thay phần lớn `Validators/`. Pydantic validate khai báo, FastAPI tự parse body.

```python
# dto/request/category_request.py
from pydantic import BaseModel, Field

class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    description: str | None = Field(default=None, max_length=255)
    parent_id: int | None = Field(default=None, gt=0)

class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=50)
    description: str | None = Field(default=None, max_length=255)
    parent_id: int | None = Field(default=None, gt=0)
```

> Đối chiếu `CategoryValidator::getConstraints()`: create yêu cầu name NotBlank + Length(3,50),
> description Optional Length(max 255), parentId Optional Positive. Map thẳng sang Field constraints.

### Response DTO — output (`dto/response/`)

Thay `App\Dto\*Dto`. Cho phép tạo từ entity (`from_attributes=True`).

```python
# dto/response/category_response.py
from pydantic import BaseModel, ConfigDict

class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    # Field tính toán (vd hierarchyPath) → xem ghi chú bên dưới
```

Dùng: `CategoryResponse.model_validate(entity)`.

## Field tính toán (computed)

`CategoryDto` PHP build `hierarchyPath` (đường dẫn cha-con) trong constructor. Pydantic không tự
duyệt quan hệ cha. Hai cách:

- **A.** Service/controller tự tính rồi truyền vào DTO (khuyến nghị — tránh lazy-load trong async).
- **B.** `@computed_field` nếu dữ liệu cha đã eager-load sẵn.

> Cẩn thận lazy-loading trong async SQLAlchemy — duyệt `parent` chưa load sẽ lỗi. Nên eager-load
> (`selectinload`/`joinedload`) hoặc tính ở tầng service.

## Khi nào vẫn cần `validator/`?

Pydantic xử lý validate cú pháp/khuôn dạng. Cần `validator/` (class được DI) khi:
- Validate cần truy vấn DB (vd: tên category đã tồn tại chưa).
- Validate cross-field phức tạp dùng chung nhiều nơi.

Đa số trường hợp PHP `Validators/` → chuyển thành Pydantic request model là đủ. Logic "ít nhất 1
trường khi update" → dùng `model_validator(mode="after")`.

## Lỗi validation → error code

PHP ném `AppException('E10711', jsonErrors)` khi validate fail. FastAPI mặc định trả 422 với cấu trúc
riêng. Cần handler để **đồng nhất** định dạng lỗi validation về dạng `{errorKey, code, message}`
nếu muốn giống PHP. Thiết kế ở Phase 1 (cùng exception handler).
