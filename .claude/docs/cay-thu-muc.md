# Cây thư mục — Shop Backend (Python/Xime, đa lớp)

```text
shop/                              ← project root
│
├── app/                           ← source root (Xime tự thêm vào sys.path)
│   ├── main.py                    ← entry point duy nhất
│   │
│   ├── config/                    ← Cấu hình framework (Python)
│   │   ├── __init__.py
│   │   ├── dependency.py          ← dependency.scan(...) các tầng
│   │   ├── routing.py             ← configure_controllers("controller")
│   │   └── security.py            ← cấu hình JWT, middleware
│   │
│   ├── controller/                ← Tầng Controller (REST) — scanned + controller
│   │   ├── __init__.py
│   │   ├── security_controller.py
│   │   ├── user_controller.py
│   │   ├── category_controller.py
│   │   ├── product_controller.py
│   │   ├── ... (mỗi controller PHP → 1 file)
│   │
│   ├── service/                   ← Tầng Service (business logic) — scanned
│   │   ├── __init__.py
│   │   ├── authentication_service.py
│   │   ├── authorization_service.py
│   │   ├── user_service.py
│   │   ├── category_service.py
│   │   ├── ...
│   │
│   ├── repository/                ← Tầng Repository (data access) — scanned
│   │   ├── __init__.py
│   │   │                            CRUD chung: kế thừa CrudRepository[T] của xime.starters.sqlalchemy
│   │   │                            (đã bỏ base_repository.py tự viết - Xime 0.6.1)
│   │   ├── user_repository.py
│   │   ├── category_repository.py
│   │   ├── ...
│   │
│   ├── entity/                    ← SQLAlchemy ORM models — EXCLUDED khỏi DI
│   │   ├── __init__.py            ← export Base + tất cả entity (cho migration); Base/TimestampMixin import thẳng từ xime.starters.sqlalchemy
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── product.py
│   │   ├── ...
│   │
│   ├── dto/                       ← Pydantic models — EXCLUDED khỏi DI
│   │   ├── __init__.py
│   │   ├── request/               ← input DTO (validate request body)
│   │   │   ├── category_request.py
│   │   │   └── ...
│   │   └── response/              ← output DTO (serialize response)
│   │       ├── category_response.py
│   │       └── ...
│   │
│   ├── validator/                 ← Validate phức tạp (nếu Pydantic chưa đủ) — scanned nếu cần inject
│   │   ├── __init__.py
│   │   └── ...
│   │
│   ├── security/                  ← Xác thực/phân quyền tầng hạ tầng — scanned
│   │   ├── __init__.py
│   │   ├── jwt_middleware.py      ← thay JwtAuthenticatorListener
│   │   └── current_user.py        ← lấy user hiện tại từ context
│   │
│   ├── exception/                 ← EXCLUDED khỏi DI
│   │   ├── __init__.py
│   │   ├── app_exception.py       ← AppException
│   │   ├── error_code.py          ← bảng error code
│   │   └── handler.py             ← map AppException → JSON response
│   │
│   └── common/                    ← Tiện ích dùng chung — thường EXCLUDED
│       ├── __init__.py
│       ├── constant/
│       └── util/
│
├── resources/                     ← Runtime config (YAML) cho operator
│   ├── application.yml            ← host, port, db url, jwt secret...
│   └── application-dev.yml
│
├── migrations/                    ← Alembic migration (nếu dùng)
│
├── test/                          ← Test code
│
├── .env                           ← biến môi trường (KHÔNG commit)
├── pyproject.toml                 ← dependency Python
└── CLAUDE.md                      ← trỏ sang .claude/
```

## Ghi chú quan trọng

- **`config/dependency.py`** khai báo các package được scan:
  ```python
  dependency.scan("controller", "service", "repository", "security")
  ```
- **`entity/`, `dto/`, `exception/`** nằm trong danh sách exclude mặc định của Xime → không bị scan vào DI. `entity` và `exception` trùng tên package exclude sẵn; `dto` cũng vậy. An toàn.
- **`controller/`** phải khai báo cả 2 nơi: `dependency.scan("controller")` (để DI tạo instance) **và** `configure_controllers("controller")` (để đăng ký route). Xem `routing-layer.md` của framework.
- **`CrudRepository[T]`** (từ `xime.starters.sqlalchemy`, Xime 0.6.1) là tương đương `Doctrine\ServiceEntityRepository` — cung cấp `find`, `find_or_fail`, `find_all`, `exists`, `count`, `save`, `save_all`, `delete` cho mọi repository kế thừa. Lớp nền là abstract nên DI scanner bỏ qua (không singleton thừa). Đã bỏ `base_repository.py` tự viết. Xem [`../rules/repository-pattern.md`](../rules/repository-pattern.md).
