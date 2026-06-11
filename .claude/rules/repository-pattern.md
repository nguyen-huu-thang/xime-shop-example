# Repository Pattern (SQLAlchemy async)

> Thay thế `Doctrine\ServiceEntityRepository`. PHP repository tự có sẵn `find`, `findAll`, `findBy`...
> Python tự viết `BaseRepository` cung cấp CRUD chung.
>
> ✅ **Đã triển khai ở Phase 1** — file thật: `app/repository/base_repository.py`. Mục dưới phản ánh
> đúng code thực tế (đã chạy + test).

## Cơ chế session của starter Xime (quan trọng)

Starter `xime.starters.sqlalchemy` KHÔNG inject `AsyncSession` trực tiếp. Thay vào đó:

- Repository inject **`AsyncSessionFactory`**, gọi `factory.current()` để lấy session đang active.
- Session **chỉ tồn tại bên trong `async with transaction()`** (mở ở service) — gọi `.current()` ngoài
  transaction sẽ **raise RuntimeError**. → Mọi thao tác repo (kể cả đọc) phải nằm trong transaction.
- `SqlAlchemyTransactionManager` lo `begin/commit/rollback`. Repo chỉ `add`/`flush`/`delete`.

## BaseRepository (code thật)

```python
# app/repository/base_repository.py
from typing import Generic, TypeVar
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from xime.starters.sqlalchemy import Base
from xime.starters.sqlalchemy.session import AsyncSessionFactory

T = TypeVar("T", bound=Base)

class BaseRepository(Generic[T]):
    model: type[T]   # subclass gán, vd: model = Category

    def __init__(self, sessions: AsyncSessionFactory) -> None:
        self._sessions = sessions

    @property
    def session(self) -> AsyncSession:
        return self._sessions.current()   # raise nếu ngoài transaction

    async def find(self, id_) -> T | None:
        return await self.session.get(self.model, id_)

    async def find_all(self) -> list[T]:
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def save(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()   # flush để lấy id; commit do transaction lo
        return entity

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()
```

> **Ghi chú:** `BaseRepository` nằm trong package `app.repository` được scan → DI tạo 1 singleton
> `BaseRepository` thừa (vô hại, không ai inject nó). Repo cụ thể được inject theo class cụ thể.

## Repository cụ thể

```python
# app/repository/category_repository.py
from sqlalchemy import select
from app.repository.base_repository import BaseRepository
from app.entity.category import Category

class CategoryRepository(BaseRepository[Category]):
    model = Category

    async def find_by_parent_id(self, parent_id: int) -> list[Category]:
        # Port từ CategoryRepository::findByParentId
        result = await self.session.execute(
            select(Category).where(Category.parent_id == parent_id)
        )
        return list(result.scalars().all())
```

## Nguyên tắc

- 1 repository ↔ 1 entity (giống PHP).
- Method query đặc thù (như `find_by_parent_id`) port 1-1 từ `createQueryBuilder` PHP.
- **Không** business logic trong repository.
- **Không** commit/rollback trong repository — đó là việc của transaction ở service.
- Repository được scan vào DI (nằm trong `repository/`), inject `AsyncSession` qua constructor.

## Vấn đề: persist/flush vs transaction

PHP: `$em->persist($x); $em->flush();` (flush ghi ngay).
Python: tách rõ —
- `repository.save()` → `add` + `flush` (đẩy xuống DB, lấy id, **chưa commit**).
- `async with service.transaction():` → commit khi thoát block không lỗi, rollback nếu có exception.

→ Service bọc thao tác ghi trong `async with self._transaction():`. Đọc thuần không cần.
