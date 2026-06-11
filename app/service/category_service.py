"""
CategoryService — quản lý danh mục cây cha-con.
Port từ CategoryService.php.
"""
from __future__ import annotations

from sqlalchemy import update as sa_update

from xime.core.transaction.manager import TransactionManager

from app.entity.category import Category
from app.entity.product import Product
from app.exception.app_exception import AppException
from app.repository.category_repository import CategoryRepository


class CategoryService:
    def __init__(
        self,
        transaction: TransactionManager,
        category_repository: CategoryRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = category_repository

    async def get_all_categories(self) -> list[Category]:
        async with self._transaction():
            return await self._repo.find_all()

    async def get_category_by_id(self, category_id: int) -> Category | None:
        async with self._transaction():
            return await self._repo.find(category_id)

    async def get_subcategories_by_parent_id(self, parent_id: int) -> list[Category]:
        async with self._transaction():
            return await self._repo.find_by_parent_id(parent_id)

    async def build_hierarchy_path(self, category: Category) -> str:
        """Walk parent chain via explicit queries; return 'Root/Parent/Child'.
        Duyệt cây cha-con bằng query rõ ràng; trả về đường dẫn tên.
        """
        names: list[str] = [category.name]
        current_parent_id = category.parent_id
        while current_parent_id is not None:
            async with self._transaction():
                parent = await self._repo.find(current_parent_id)
            if not parent:
                break
            names.append(parent.name)
            current_parent_id = parent.parent_id
        return "/".join(reversed(names))

    async def build_hierarchy_path_by_id(self, category: Category) -> str:
        """Walk parent chain; return '1/3/7' style id path.
        Duyệt cây cha-con; trả về đường dẫn ID.
        """
        ids: list[str] = [str(category.id)]
        current_parent_id = category.parent_id
        while current_parent_id is not None:
            async with self._transaction():
                parent = await self._repo.find(current_parent_id)
            if not parent:
                break
            ids.append(str(parent.id))
            current_parent_id = parent.parent_id
        return "/".join(reversed(ids))

    async def create_category(self, data: dict) -> Category:
        name = data.get("name") or ""
        if not name:
            raise AppException("E10301")

        parent_id: int | None = data.get("parent_id") or data.get("parentId")
        if parent_id:
            async with self._transaction():
                parent = await self._repo.find(parent_id)
            if not parent:
                raise AppException("E10300")

        async with self._transaction():
            cat = Category(
                name=name,
                description=data.get("description"),
                parent_id=parent_id,
            )
            return await self._repo.save(cat)

    async def update_category(self, category_id: int, data: dict) -> Category:
        async with self._transaction():
            cat = await self._repo.find(category_id)
        if not cat:
            raise AppException("E10300")

        if data.get("name"):
            cat.name = data["name"]
        if data.get("description") is not None:
            cat.description = data["description"]

        raw_parent = data.get("parentId", data.get("parent_id", "__MISSING__"))
        if raw_parent != "__MISSING__":
            if raw_parent:
                async with self._transaction():
                    parent = await self._repo.find(raw_parent)
                if not parent:
                    raise AppException("E10300")
            cat.parent_id = raw_parent if raw_parent else None

        async with self._transaction():
            return await self._repo.save(cat)

    async def delete_category(self, category_id: int) -> None:
        """Reassign children + products to parent, then delete category.
        Gán danh mục con + sản phẩm về parent, rồi xóa danh mục.
        """
        async with self._transaction():
            cat = await self._repo.find(category_id)
        if not cat:
            raise AppException("E10300")

        parent_id = cat.parent_id

        async with self._transaction():
            # Reassign children to parent
            # Gán các danh mục con về parent
            children = await self._repo.find_by_parent_id(category_id)
            for child in children:
                child.parent_id = parent_id
                await self._repo.save(child)

            # Reassign products to parent using bulk UPDATE
            # Cập nhật category_id của sản phẩm sang parent bằng bulk UPDATE
            await self._repo.session.execute(
                sa_update(Product)
                .where(Product.category_id == category_id)
                .values(category_id=parent_id)
            )

            category = await self._repo.find(category_id)
            if category:
                await self._repo.delete(category)

    async def find_products_by_category_id(self, category_id: int) -> list[Product]:
        """Return raw product entities for a category (used by ProductService).
        Trả về entity sản phẩm theo danh mục.
        """
        from sqlalchemy import select
        async with self._transaction():
            result = await self._repo.session.execute(
                select(Product).where(Product.category_id == category_id)
            )
            return list(result.scalars().all())
