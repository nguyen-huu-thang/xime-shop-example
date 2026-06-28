"""
DTO phản hồi cho dashboard quản trị.
"""
from __future__ import annotations

from pydantic import BaseModel


class TopProduct(BaseModel):
    productId: int
    name: str
    totalSold: int


class DashboardStats(BaseModel):
    revenuePaid: float          # tổng doanh thu đơn đã thanh toán
    totalOrders: int            # tổng số đơn
    ordersToday: int            # số đơn tạo hôm nay (UTC)
    unpaidOrders: int           # số đơn chưa thanh toán
    totalProducts: int          # số sản phẩm còn (chưa xóa mềm)
    lowStockOptions: int        # số option tồn kho dưới ngưỡng
    totalUsers: int             # số người dùng
    totalReviews: int           # số đánh giá
    topProducts: list[TopProduct]  # sản phẩm bán chạy
