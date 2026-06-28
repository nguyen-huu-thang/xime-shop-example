from __future__ import annotations

from sqlalchemy import func, or_, select

from app.entity.product import Product
from app.repository.base_repository import BaseRepository


class ProductRepository(BaseRepository[Product]):
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

    async def find_all_paginated(self, page: int, limit: int) -> list[Product]:
        # Only return non-deleted products
        # Chỉ trả về sản phẩm chưa bị xóa mềm
        offset = (page - 1) * limit
        result = await self.session.execute(
            select(Product)
            .where(Product.is_delete.is_(False))
            .order_by(Product.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

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
