"""
CooccurrenceRebuildJob - job định kỳ dựng lại bảng "mua cùng" (co-occurrence).

Chạy bởi Xime scheduler theo lịch khai báo trong app/config/scheduler.py. Constructor injection
hoạt động bình thường: khai báo phụ thuộc trong __init__, DI container resolve trước khi scheduler chạy.
Package "app.job" đã nằm trong dependency.scan(...) nên job class được DI resolve khi cron chạy.
"""
from __future__ import annotations

import logging

from app.service.cooccurrence_service import CooccurrenceService

logger = logging.getLogger(__name__)


class CooccurrenceRebuildJob:
    def __init__(self, cooccurrence_service: CooccurrenceService) -> None:
        self._cooccurrence = cooccurrence_service

    async def run(self) -> None:
        # Scheduler gọi định kỳ; dựng lại toàn bộ bảng từ order_details.
        # Called periodically by the scheduler; full rebuild from order_details.
        written = await self._cooccurrence.rebuild()
        logger.info("Co-occurrence rebuilt by scheduler: %s rows", written)
