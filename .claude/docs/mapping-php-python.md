# Mapping PHP/Symfony → Python/Xime

Bảng tra cứu khi chuyển từng thành phần. Mục tiêu: giữ nghiệp vụ, đổi cú pháp + idiom.

## Tầng & class

| PHP | Python | Ghi chú |
|---|---|---|
| `App\Controller\Api\XController` (extends `AbstractController`) | `controller/x_controller.py` class `XController` | Class-based, dùng decorator `@get/@post`. Không kế thừa base nào của framework. |
| `App\Service\XService` | `service/x_service.py` class `XService` | Constructor injection. |
| `App\Repository\XRepository` (extends `ServiceEntityRepository`) | `repository/x_repository.py` class `XRepository(BaseRepository)` | Kế thừa `BaseRepository` tự viết. |
| `App\Entity\X` (Doctrine attrs) | `entity/x.py` class `X(Base)` | SQLAlchemy `Mapped`/`mapped_column`. |
| `App\Dto\XDto` | `dto/response/x_response.py` (Pydantic) | Output. Input → `dto/request/`. |
| `App\Validators\XValidator` | Pydantic request model (đa số) hoặc `validator/x_validator.py` | Xem [`../rules/dto-va-validation.md`](../rules/dto-va-validation.md). |
| `App\Exception\AppException` | `exception/app_exception.py` `AppException` | Giữ cơ chế error key. |
| `App\Exception\ErrorCode` | `exception/error_code.py` | Giữ nguyên bảng mã. |
| `App\EventListener\JwtAuthenticatorListener` | `security/jwt_middleware.py` | Web middleware. |
| `App\Command\SetupInitialCommand` | script seed (CLI Xime hoặc `python -m ...`) | Seed quyền + admin. |

## Cú pháp & idiom

| PHP | Python |
|---|---|
| `private XService $svc;` + gán trong `__construct` | `def __init__(self, svc: XService): self._svc = svc` |
| `$this->repo->find($id)` | `await self._repo.find(id)` (async) |
| `$em->persist($x); $em->flush();` | `async with self.transaction(): await self._repo.save(x)` |
| `json_decode($request->getContent(), true)` | tham số `body: XRequest` (Pydantic tự parse) |
| `$this->json($dto, 201)` | `return XResponse.model_validate(entity)` + `status_code=201` trong decorator |
| `throw new AppException('E2021')` | `raise AppException("E2021")` |
| `$request->attributes->get('user')` | `current_user()` từ context (xem [`auth-jwt.md`](auth-jwt.md)) |
| `array_map(fn($c) => new CategoryDto($c), $list)` | `[CategoryResponse.model_validate(c) for c in items]` |
| `#[Route('/api/categories')]` trên class | `prefix = "/api/categories"` thuộc class controller |
| `#[Route('/{id}', methods:['GET'])]` | `@get("/{id}")` trên method |
| `password_hash` / `password_verify` (PHP) | `passlib`/`bcrypt` — **phải kiểm tra thuật toán hash PHP dùng** để verify tương thích |

## Doctrine → SQLAlchemy

| Doctrine | SQLAlchemy (async) |
|---|---|
| `#[ORM\Entity]` `#[ORM\Table('users')]` | `class User(Base): __tablename__ = "users"` |
| `#[ORM\Id] #[ORM\GeneratedValue] #[ORM\Column(type:'bigint')]` | `id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)` |
| `#[ORM\Column(type:'string', length:255, unique:true)]` | `mapped_column(String(255), unique=True)` |
| `#[ORM\ManyToOne(targetEntity: User::class)]` | `relationship()` + `mapped_column(ForeignKey("users.id"))` |
| `$repo->findAll()` | `await session.execute(select(X))` → `.scalars().all()` |
| `$repo->find($id)` | `await session.get(X, id)` |
| `createQueryBuilder('c')->andWhere(...)` | `select(X).where(...)` |
| `$em->remove($x)` | `await session.delete(x)` |

## Phân quyền (mẫu lặp lại trong mọi controller PHP)

PHP:
```php
$userCurrent = $request->attributes->get('user');
if (!$userCurrent) throw new AppException('E2025');
if (!$this->authorizationService->checkPermission($userCurrent, "create_category"))
    throw new AppException('E2021');
```

Python (đề xuất — gói lại cho gọn):
```python
user = current_user()                      # raise E2025 nếu chưa đăng nhập
await self._authz.require(user, "create_category")   # raise E2021 nếu thiếu quyền
```

> Thiết kế chi tiết: [`phan-quyen.md`](phan-quyen.md). Có thể giữ y hệt PHP (gọi `check_permission`
> rồi tự `raise`) cho sát bản gốc, hoặc bọc thành helper `require()`. **Khuyến nghị bọc helper** để
> giảm lặp code 18 controller.
