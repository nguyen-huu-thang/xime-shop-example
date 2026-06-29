# Issue #3 — Thêm BaseRepository/CRUD chung vào starter SQLAlchemy

> **ĐÃ GIẢI QUYẾT PHÍA FRAMEWORK (Xime 0.6.1, 2026-06-29).**
> Framework đã thêm `xime.starters.sqlalchemy.CrudRepository[T]` với 8 method:
> `find` · `find_or_fail` · `find_all` · `exists` · `count` · `save` · `save_all`
> · `delete`, cùng exception `EntityNotFoundError` cho `find_or_fail`.
> `model` là abstract property nên lớp nền là abstract -> DI scanner bỏ qua, hết
> singleton thừa; chỉ subclass set `model` mới vào DI.
>
> **Việc cần làm trong shop khi nâng Xime lên 0.6.1:**
> 1. Đổi mọi repository con sang `class XxxRepository(CrudRepository[Xxx]): model = Xxx`.
> 2. Xóa `app/repository/base_repository.py` tự viết.
> 3. Hết luôn singleton `BaseRepository` thừa.
>
> Lưu ý API có khác base tự viết: framework đặt tên `find` (không phải `find` cũ
> đã trùng), thêm `find_or_fail/exists/count/save_all`. Query đặc thù vẫn tự viết
> bằng `select()` qua `self.session`.

- **Mức độ:** Trung bình (đề xuất tính năng, giảm boilerplate cho mọi app)
- **Phase phát hiện:** Pha tối ưu (rà code chết sau migrate)
- **Thành phần:** `xime.starters.sqlalchemy`
- **Liên quan:** cơ chế loại trừ DI trong `xime/core/container/scanner.py`

## Bối cảnh

Spring Data JPA cho sẵn `JpaRepository<T, ID>` / `CrudRepository<T, ID>`: chỉ cần khai báo
interface là có ngay `findById`, `findAll`, `save`, `delete`, `count`... Framework sinh
implementation lúc runtime.

SQLAlchemy KHÔNG có lớp này - nó là ORM/query toolkit mức thấp (`session.get`, `session.execute`).
Hệ quả: **mỗi app dùng Xime tự viết lại một `BaseRepository` gần như giống hệt nhau** rồi cho
mọi repository kế thừa. Trong shop là `app/repository/base_repository.py`:

```python
T = TypeVar("T", bound=Base)

class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, sessions: AsyncSessionFactory) -> None:
        self._sessions = sessions

    @property
    def session(self) -> AsyncSession:
        return self._sessions.current()

    async def find(self, id_) -> T | None:
        return await self.session.get(self.model, id_)

    async def find_all(self) -> list[T]:
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def save(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()
```

Đoạn này lặp lại ở **mọi dự án** trong nhóm Monolithic (shop, dental-clinic, auto-garage,
english-center, rental-management, spa) - đúng kiểu boilerplate framework nên gánh.

## Vấn đề phụ: BaseRepository tự viết bị DI tạo singleton thừa

Vì `BaseRepository` nằm trong package `app.repository` được `dependency.scan(...)`, scanner coi nó
là class đủ điều kiện (init có type-hint đủ, không Protocol, không abstract) -> DI tạo **1 singleton
`BaseRepository` không ai inject**. Vô hại nhưng bẩn. Nếu framework cung cấp sẵn base này thì:

- App không còn tự định nghĩa base trong package bị scan -> hết singleton thừa.
- Base của framework đặt ngoài package app nên không bị scanner của app quét.

## Đề xuất cho framework

### 1. Cung cấp `CrudRepository[T]` (hoặc `BaseRepository[T]`) trong `xime.starters.sqlalchemy`

```python
# xime/starters/sqlalchemy/repository.py
from abc import ABC
from typing import Generic, TypeVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from xime.starters.sqlalchemy import Base
from xime.starters.sqlalchemy.session import AsyncSessionFactory

T = TypeVar("T", bound=Base)

class CrudRepository(Generic[T], ABC):   # ABC -> scanner bỏ qua (xem mục 2)
    model: type[T]

    def __init__(self, sessions: AsyncSessionFactory) -> None:
        self._sessions = sessions

    @property
    def session(self) -> AsyncSession:
        return self._sessions.current()

    async def find(self, id_) -> T | None: ...
    async def find_all(self) -> list[T]: ...
    async def save(self, entity: T) -> T: ...
    async def delete(self, entity: T) -> None: ...
    async def count(self) -> int: ...
```

App chỉ cần:

```python
from xime.starters.sqlalchemy import CrudRepository

class CategoryRepository(CrudRepository[Category]):
    model = Category
    # chỉ viết thêm query đặc thù
```

Phạm vi tối giản: `find/find_all/save/delete/count` là đủ cho 90% nhu cầu. KHÔNG cần derived query
kiểu Spring (`findByEmail`) - giữ đơn giản, query đặc thù để app tự viết bằng `select()`.

### 2. Đảm bảo base này KHÔNG bị đăng ký vào DI

`CrudRepository` là lớp nền generic, không bao giờ instantiate trực tiếp. Cho kế thừa `abc.ABC`
(có ít nhất 1 `@abstractmethod`, hoặc dùng cơ chế tương đương) để `scanner._is_eligible` bỏ qua nó
qua nhánh `is_abstract`. Như vậy chỉ các repository con cụ thể (đã set `model`) mới vào DI.

> Ghi chú: hiện scanner loại class theo: segment module bị cấm (`domain/dto/entity/vo/constant/
> exception`), `__all__` whitelist trong `__init__.py`, Protocol, abstract (ABC), hoặc thiếu
> type-hint. Base nằm trong package framework nên cũng không bị app quét. Nhưng nếu app vẫn import
> và subclass, bản thân base abstract sẽ không bị đăng ký - an toàn.

### 3. (Tùy chọn) Tài liệu di trú

Ghi chú trong CHANGELOG + docs: app đang tự viết `BaseRepository` có thể đổi sang
`xime.starters.sqlalchemy.CrudRepository` và xóa file tự viết.

## Workaround hiện tại trong shop

Vẫn dùng `app/repository/base_repository.py` tự viết. Khi framework có `CrudRepository`, sẽ:
1. Đổi các repository con sang kế thừa `CrudRepository[...]`.
2. Xóa `app/repository/base_repository.py`.
3. Hết luôn singleton `BaseRepository` thừa.
