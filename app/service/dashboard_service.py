"""
DashboardService - tổng hợp số liệu cho trang quản trị shop.

Tất cả truy vấn gom trong MỘT transaction đọc.
"""
from __future__ import annotations

from datetime import UTC, datetime, time

from xime.core.transaction.manager import TransactionManager

from app.dto.response.dashboard_response import DashboardStats, TopProduct
from app.repository.order_detail_repository import OrderDetailRepository
from app.repository.order_repository import OrderRepository
from app.repository.product_option_repository import ProductOptionRepository
from app.repository.product_repository import ProductRepository
from app.repository.review_repository import ReviewRepository
from app.repository.user_repository import UserRepository

# Ngưỡng cảnh báo tồn kho thấp.
# Low-stock warning threshold.
_LOW_STOCK_THRESHOLD = 10
_TOP_PRODUCTS_LIMIT = 5


class DashboardService:
    def __init__(
        self,
        transaction: TransactionManager,
        order_repository: OrderRepository,
        order_detail_repository: OrderDetailRepository,
        product_repository: ProductRepository,
        product_option_repository: ProductOptionRepository,
        user_repository: UserRepository,
        review_repository: ReviewRepository,
    ) -> None:
        self._transaction = transaction
        self._order_repo = order_repository
        self._detail_repo = order_detail_repository
        self._product_repo = product_repository
        self._option_repo = product_option_repository
        self._user_repo = user_repository
        self._review_repo = review_repository

    async def get_stats(self) -> DashboardStats:
        # Mốc "hôm nay" theo UTC.
        # "Today" boundary in UTC.
        now = datetime.now(UTC)
        start_today = datetime.combine(now.date(), time.min, tzinfo=UTC)

        async with self._transaction():
            revenue_paid = await self._order_repo.revenue_paid()
            total_orders = await self._order_repo.count()
            orders_today = await self._order_repo.count_created_since(start_today)
            unpaid_orders = await self._order_repo.count_unpaid()
            total_products = await self._product_repo.count_active()
            low_stock = await self._option_repo.count_low_stock(_LOW_STOCK_THRESHOLD)
            total_users = await self._user_repo.count()
            total_reviews = await self._review_repo.count()
            top = await self._detail_repo.top_selling(_TOP_PRODUCTS_LIMIT)

        return DashboardStats(
            revenuePaid=revenue_paid,
            totalOrders=total_orders,
            ordersToday=orders_today,
            unpaidOrders=unpaid_orders,
            totalProducts=total_products,
            lowStockOptions=low_stock,
            totalUsers=total_users,
            totalReviews=total_reviews,
            topProducts=[
                TopProduct(productId=pid, name=name, totalSold=qty)
                for pid, name, qty in top
            ],
        )
