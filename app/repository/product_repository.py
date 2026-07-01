from __future__ import annotations

from sqlalchemy import func, or_, select

from app.entity.product import Product
from app.utils.pagination import paginate
from xime.starters.sqlalchemy import CrudRepository


class ProductRepository(CrudRepository[Product]):
    model = Product

    async def count_active(self) -> int:
        # Đếm sản phẩm chưa bị xóa mềm.
        # Count non-soft-deleted products.
        result = await self.session.execute(
            select(func.count()).select_from(Product).where(Product.is_delete.is_(False))
        )
        return int(result.scalar_one())

    async def find_by_category_id(self, category_id: int) -> list[Product]:
        result = await self.session.execute(
            select(Product).where(Product.category_id == category_id)
        )
        return list(result.scalars().all())

    async def find_by_ids(self, product_ids: set[int]) -> list[Product]:
        # Lấy sản phẩm chưa xóa theo tập id (cho gợi ý dựng DTO theo id).
        # Fetch non-deleted products by id set (for building recommendation DTOs).
        if not product_ids:
            return []
        result = await self.session.execute(
            select(Product)
            .where(Product.id.in_(product_ids))
            .where(Product.is_delete.is_(False))
        )
        return list(result.scalars().all())

    async def find_all_paginated(self, page: int, limit: int) -> list[Product]:
        # Only return non-deleted products
        # Chỉ trả về sản phẩm chưa bị xóa mềm
        offset, limit = paginate(page, limit)
        result = await self.session.execute(
            select(Product)
            .where(Product.is_delete.is_(False))
            .order_by(Product.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def find_paginated_in_categories(
        self, category_ids: set[int], page: int, limit: int
    ) -> list[Product]:
        # Sản phẩm chưa xóa, thuộc các category cho phép (lọc theo mảng nhân viên)
        # Non-deleted products within the allowed categories (employee-scope filter)
        if not category_ids:
            return []
        offset, limit = paginate(page, limit)
        result = await self.session.execute(
            select(Product)
            .where(Product.is_delete.is_(False))
            .where(Product.category_id.in_(category_ids))
            .order_by(Product.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_active_in_categories(self, category_ids: set[int]) -> int:
        if not category_ids:
            return 0
        result = await self.session.execute(
            select(func.count())
            .select_from(Product)
            .where(Product.is_delete.is_(False))
            .where(Product.category_id.in_(category_ids))
        )
        return int(result.scalar_one())

    async def search_by_keywords(self, keywords: str) -> list[Product]:
        pattern = f"%{keywords}%"
        result = await self.session.execute(
            select(Product)
            .where(Product.is_delete.is_(False))
            .where(
                or_(Product.name.ilike(pattern), Product.description.ilike(pattern))
            )
            .order_by(Product.id.asc())
        )
        return list(result.scalars().all())
