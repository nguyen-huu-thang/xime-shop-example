"""
ExpireOrdersJob - job định kỳ hủy đơn online quá hạn thanh toán và HOÀN KHO lại.

Chạy bởi Xime scheduler theo lịch trong app/config/scheduler.py. Giữ chỗ tồn kho kiểu Shopee:
đơn online trừ kho ngay lúc đặt; nếu quá hạn (payment_deadline) chưa thanh toán thì job này
cộng lại tồn kho + nhả lượt dùng coupon + đánh dấu đơn đã hủy.
"""
from __future__ import annotations

import logging

from app.service.order_service import OrderService

logger = logging.getLogger(__name__)


class ExpireOrdersJob:
    def __init__(self, order_service: OrderService) -> None:
        self._svc = order_service

    async def run(self) -> None:
        cancelled = await self._svc.expire_overdue_online_orders()
        if cancelled:
            logger.info("Expired %s overdue online order(s), stock restored", cancelled)
