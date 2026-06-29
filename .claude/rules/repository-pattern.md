# Repository Pattern (SQLAlchemy async)

> Thay thế `Doctrine\ServiceEntityRepository`. PHP repository tự có sẵn `find`, `findAll`, `findBy`...
> Python kế thừa **`CrudRepository[T]` của framework** (`xime.starters.sqlalchemy`) để có sẵn CRUD chung.
>
> ✅ **Cập nhật (Xime 0.6.1):** trước đây dùng `app/repository/base_repository.py` tự viết; nay đã
> đổi sang `CrudRepository[T]` do framework cung cấp và **xóa file base tự viết**. `CrudRepository` là
> abstract (`model` là abstract property) nên DI scanner bỏ qua lớp nền -> hết singleton thừa.

## Cơ chế session của starter Xime (quan trọng)

Starter `xime.starters.sqlalchemy` KHÔNG inject `AsyncSession` trực tiếp. Thay vào đó:

- Repository inject **`AsyncSessionFactory`**, gọi `factory.current()` để lấy session đang active.
- Session **chỉ tồn tại bên trong `async with transaction()`** (mở ở service) — gọi `.current()` ngoài
  transaction sẽ **raise RuntimeError**. → Mọi thao tác repo (kể cả đọc) phải nằm trong transaction.
- `SqlAlchemyTransactionManager` lo `begin/commit/rollback`. Repo chỉ `add`/`flush`/`delete`.

## CrudRepository của framework (Xime 0.6.1)

Base CRUD do `xime.starters.sqlalchemy` cung cấp - app không tự viết nữa. Method có sẵn:
`find` · `find_or_fail` · `find_all` · `exists` · `count` · `save` · `save_all` · `delete`, cùng
exception `EntityNotFoundError` (cho `find_or_fail`).

Cơ chế: `model` là abstract property nên chính `CrudRepository` là abstract -> DI scanner bỏ qua
lớp nền. Subclass set `model = Entity` (class attribute) tự thành concrete và được đăng ký - không
còn singleton base thừa như bản tự viết trước đây. `session` đọc qua `AsyncSessionFactory.current()`
nên mọi method phải gọi trong `async with transaction()` (mở ở service).

## Repository cụ thể

```python
# app/repository/category_repository.py
from sqlalchemy import select
from xime.starters.sqlalchemy import CrudRepository
from app.entity.category import Category

class CategoryRepository(CrudRepository[Category]):
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
