"""
CategoryService - quản lý danh mục cây cha-con.
Port từ CategoryService.php.
"""
from __future__ import annotations

from sqlalchemy import update as sa_update

from xime.core.transaction.manager import TransactionManager

from app.cache.category_tree_cache import CategoryTreeCache
from app.entity.category import Category
from app.entity.product import Product
from app.exception.app_exception import AppException
from app.repository.category_repository import CategoryRepository


class CategoryService:
    def __init__(
        self,
        transaction: TransactionManager,
        category_repository: CategoryRepository,
        category_tree_cache: CategoryTreeCache,
    ) -> None:
        self._transaction = transaction
        self._repo = category_repository
        self._tree_cache = category_tree_cache

    async def _ensure_tree_loaded(self) -> None:
        # Nạp cây category vào RAM lần đầu (hoặc sau invalidate)
        # Load the category tree into RAM on first use (or after invalidate)
        if not self._tree_cache.is_loaded():
            async with self._transaction():
                cats = await self._repo.find_all()
            self._tree_cache.load([(c.id, c.parent_id) for c in cats])

    async def get_ancestor_ids(self, category_id: int) -> list[int]:
        """Chuỗi tổ tiên gồm cả chính nó: [category_id, parent, ..., root].
        Dùng cho phân quyền theo nhánh - khớp target là category cha."""
        await self._ensure_tree_loaded()
        return self._tree_cache.ancestor_ids(category_id)

    async def get_descendant_ids(self, category_id: int) -> set[int]:
        """Tập category_id + toàn bộ con cháu - dùng cho lọc danh sách theo nhánh."""
        await self._ensure_tree_loaded()
        return self._tree_cache.descendant_ids(category_id)

    async def get_all_category_ids(self) -> set[int]:
        """Tất cả category id - dùng để tính tập category được phép khi lọc danh sách."""
        await self._ensure_tree_loaded()
        return self._tree_cache.all_ids()

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
        Duyệt cây cha-con bằng một transaction duy nhất; trả về đường dẫn tên.
        """
        names: list[str] = [category.name]
        current_parent_id = category.parent_id
        # Use a single transaction for the entire tree walk
        # Dùng một transaction duy nhất cho toàn bộ quá trình duyệt cây
        async with self._transaction():
            while current_parent_id is not None:
                parent = await self._repo.find(current_parent_id)
                if not parent:
                    break
                names.append(parent.name)
                current_parent_id = parent.parent_id
        return "/".join(reversed(names))

    async def build_hierarchy_path_by_id(self, category: Category) -> str:
        """Walk parent chain; return '1/3/7' style id path.
        Duyệt cây cha-con trong một transaction; trả về đường dẫn ID.
        """
        ids: list[str] = [str(category.id)]
        current_parent_id = category.parent_id
        # Use a single transaction for the entire tree walk
        # Dùng một transaction duy nhất cho toàn bộ quá trình duyệt cây
        async with self._transaction():
            while current_parent_id is not None:
                parent = await self._repo.find(current_parent_id)
                if not parent:
                    break
                ids.append(str(parent.id))
                current_parent_id = parent.parent_id
        return "/".join(reversed(ids))

    async def create_category(self, data: dict) -> Category:
        name = data.get("name") or ""
        if not name:
            raise AppException("E10311")  # Category name required

        parent_id: int | None = data.get("parent_id") or data.get("parentId")
        if parent_id:
            async with self._transaction():
                parent = await self._repo.find(parent_id)
            if not parent:
                raise AppException("E10310")  # Category not found

        async with self._transaction():
            cat = Category(
                name=name,
                description=data.get("description"),
                parent_id=parent_id,
            )
            await self._repo.save(cat)
        # Cây thay đổi -> invalidate cache (sau commit)
        # Tree changed -> invalidate cache (after commit)
        self._tree_cache.invalidate()
        return cat

    async def update_category(self, category_id: int, data: dict) -> Category:
        async with self._transaction():
            cat = await self._repo.find(category_id)
        if not cat:
            raise AppException("E10310")  # Category not found

        if data.get("name"):
            cat.name = data["name"]
        if data.get("description") is not None:
            cat.description = data["description"]

        # Check if parent_id key is present at all (None = clear, missing key = no change)
        # Kiểm tra xem key parent_id có trong data không (None = xóa parent, thiếu key = không đổi)
        parent_key = "parentId" if "parentId" in data else ("parent_id" if "parent_id" in data else None)
        if parent_key is not None:
            raw_parent = data[parent_key]
            if raw_parent:
                async with self._transaction():
                    parent = await self._repo.find(raw_parent)
                if not parent:
                    raise AppException("E10310")  # Category not found
            cat.parent_id = raw_parent if raw_parent else None

        async with self._transaction():
            await self._repo.save(cat)
        # Cây có thể đổi parent -> invalidate cache (sau commit)
        # Parent may have changed -> invalidate cache (after commit)
        self._tree_cache.invalidate()
        return cat

    async def delete_category(self, category_id: int) -> None:
        """Reassign children + products to parent, then delete category.
        Gán danh mục con + sản phẩm về parent, rồi xóa danh mục.
        """
        async with self._transaction():
            cat = await self._repo.find(category_id)
        if not cat:
            raise AppException("E10310")  # Category not found

        parent_id = cat.parent_id

        async with self._transaction():
            # Reassign children to parent
            # Gán các danh mục con về parent
            children = await self._repo.find_by_parent_id(category_id)
            for child in children:
                child.parent_id = parent_id
            # Một flush cho cả lô con thay vì flush từng cái
            # One flush for the whole batch instead of per child
            await self._repo.save_all(children)

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
        # Cây thay đổi (xóa node + đổi parent con/sản phẩm) -> invalidate cache (sau commit)
        # Tree changed (node removed + children/products reparented) -> invalidate cache
        self._tree_cache.invalidate()

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
