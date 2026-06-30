from __future__ import annotations

from sqlalchemy import delete, select

from app.entity.product_cooccurrence import ProductCooccurrence
from xime.starters.sqlalchemy import CrudRepository


class ProductCooccurrenceRepository(CrudRepository[ProductCooccurrence]):
    model = ProductCooccurrence

    async def top_related_ids(self, product_id: int, limit: int) -> list[int]:
        # Sản phẩm liên quan tới `product_id`, theo số lần đồng xuất hiện giảm dần.
        # Products related to `product_id`, ordered by co-occurrence count desc.
        result = await self.session.execute(
            select(ProductCooccurrence.related_product_id)
            .where(ProductCooccurrence.product_id == product_id)
            .order_by(ProductCooccurrence.count.desc())
            .limit(limit)
        )
        return [int(row[0]) for row in result.all()]

    async def delete_all(self) -> None:
        # Xóa sạch để dựng lại (rebuild batch). Chạy trong transaction của service.
        # Truncate-by-delete before a full rebuild.
        await self.session.execute(delete(ProductCooccurrence))

    async def insert_rows(self, rows: list[tuple[int, int, int]]) -> None:
        # Chèn hàng loạt (product_id, related_product_id, count).
        # Bulk insert co-occurrence rows.
        for product_id, related_id, count in rows:
            self.session.add(
                ProductCooccurrence(
                    product_id=product_id,
                    related_product_id=related_id,
                    count=count,
                )
            )
        await self.session.flush()
