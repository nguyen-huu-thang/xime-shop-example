"""
CooccurrenceService - "mua/xem cùng" theo đồng mua (co-purchase), materialized.

Tính tăng dần mỗi sự kiện rất tốn (ghép sản phẩm mới với mọi sản phẩm trong lịch sử), nên
dựng lại theo BATCH: quét order_details, với mỗi đơn sinh các cặp sản phẩm có hướng, đếm số đơn
chứa cả hai, ghi đè bảng product_cooccurrence. Lịch chạy do Xime scheduler (xem config/scheduler.py);
có thể dựng lại thủ công qua endpoint admin.

Nguồn: đồng mua trong cùng đơn (order_details) - tín hiệu mạnh, ít nhiễu.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.repository.order_detail_repository import OrderDetailRepository
from app.repository.product_cooccurrence_repository import (
    ProductCooccurrenceRepository,
)


class CooccurrenceService:
    def __init__(
        self,
        transaction: TransactionManager,
        product_cooccurrence_repository: ProductCooccurrenceRepository,
        order_detail_repository: OrderDetailRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = product_cooccurrence_repository
        self._order_detail_repo = order_detail_repository

    @staticmethod
    def _count_cooccurrence(
        order_product_pairs: list[tuple[int, int]]
    ) -> list[tuple[int, int, int]]:
        """Từ các cặp (order_id, product_id) -> list (product_id, related_id, count).

        count = số đơn chứa cả hai sản phẩm. Cặp có hướng (a,b) và (b,a) đều được lưu để
        truy vấn "liên quan tới a" chỉ cần WHERE product_id=a. Thuần RAM, không I/O.
        """
        products_by_order: dict[int, set[int]] = {}
        for order_id, product_id in order_product_pairs:
            products_by_order.setdefault(order_id, set()).add(product_id)

        counts: dict[tuple[int, int], int] = {}
        for products in products_by_order.values():
            items = list(products)
            for i in range(len(items)):
                for j in range(len(items)):
                    if i == j:
                        continue
                    key = (items[i], items[j])
                    counts[key] = counts.get(key, 0) + 1
        return [(a, b, c) for (a, b), c in counts.items()]

    async def rebuild(self) -> int:
        """Dựng lại toàn bộ bảng co-occurrence từ order_details. Trả số dòng đã ghi."""
        async with self._transaction():
            pairs = await self._order_detail_repo.all_order_product_pairs()
            rows = self._count_cooccurrence(pairs)
            await self._repo.delete_all()
            if rows:
                await self._repo.insert_rows(rows)
        return len(rows)

    async def get_related_product_ids(
        self, product_id: int, limit: int = 10
    ) -> list[int]:
        """Id sản phẩm hay được mua cùng `product_id`, nhiều nhất trước."""
        async with self._transaction():
            return await self._repo.top_related_ids(product_id, limit)
