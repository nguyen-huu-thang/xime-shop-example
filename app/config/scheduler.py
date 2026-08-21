"""
Cấu hình Xime scheduler cho Shop Backend (ĐÃ KÍCH HOẠT).

Framework Application tự nạp mọi module trong package `app.config` lúc khởi động, nên file này
chạy configure_scheduler() tự động. StartupOrchestrator dựng SchedulerRunner từ registry (cần
apscheduler v4 - đã cài 4.0.0a6). Job class được resolve qua DI nên package "app.job" phải nằm
trong dependency.scan(...) (đã thêm ở config/dependency.py).

Lịch: dựng lại bảng co-occurrence mỗi ngày lúc 03:00 (giờ VN). Chỉnh cron tùy nhu cầu.
Dựng lại thủ công bất cứ lúc nào: POST /api/recommendations/admin/rebuild-cooccurrence.
"""
from __future__ import annotations

import sys

from xime.starters.lmdb import StoreCleanupJob
from xime.starters.scheduler import (
    CronJob,
    IntervalJob,
    SchedulerConfig,
    configure_scheduler,
)

from app.job.cooccurrence_rebuild_job import CooccurrenceRebuildJob
from app.job.expire_orders_job import ExpireOrdersJob

# Không chạy scheduler khi test: AsyncScheduler khởi động trong mỗi TestApplication và không được
# tắt sạch giữa các test (event loop đóng), gây nhiễu chéo. Prod (python -m app.main) không nạp
# pytest nên scheduler hoạt động bình thường. Dựng lại thủ công vẫn được qua endpoint admin.
# Skip the scheduler under pytest (it leaks across test event loops); it runs normally in prod.
if "pytest" not in sys.modules:
    configure_scheduler(
        SchedulerConfig(
            jobs=[
                # 03:00 hằng ngày - giờ thấp điểm, dựng lại "mua cùng" từ order_details
                # Daily at 03:00 (off-peak) - rebuild co-occurrence from order_details
                CronJob(job_class=CooccurrenceRebuildJob, cron="0 3 * * *"),
                # Mỗi 10 phút - hủy đơn online quá hạn thanh toán + hoàn kho (giữ chỗ hết hạn)
                # Every 10 minutes - cancel overdue online orders + restore reserved stock
                CronJob(job_class=ExpireOrdersJob, cron="*/10 * * * *"),
                # Mỗi 10 phút - dọn bản ghi hết hạn trong kho Xime Store (LMDB).
                # Không ảnh hưởng tính đúng đắn (bản ghi hết hạn đã vô hình với get()), chỉ thu
                # hồi chỗ. Từ Xime 0.8 scheduler là adapter hạng đơn nhất nên nó chỉ chạy ở
                # tiến trình primary - ghi LMDB là độc quyền theo file, N tiến trình cùng quét
                # thì N-1 chỉ xếp hàng chờ khóa ghi.
                # Every 10 minutes - reclaim space from expired store entries (primary only).
                IntervalJob(job_class=StoreCleanupJob, minutes=10),
            ],
            timezone="Asia/Ho_Chi_Minh",
        )
    )
