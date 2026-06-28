from xime import BindingConfig
from xime.core.transaction.manager import TransactionManager
from xime.starters.cache import CacheService
from xime.starters.localfs import LocalFileStorage
from xime.starters.sqlalchemy import SqlAlchemyTransactionManager
from xime.starters.storage import StorageService

from app.cache.in_memory_cache_service import InMemoryCacheService

# ── Cấu hình Dependency Injection cho Shop Backend ───────────────────────────
# Framework đọc biến `dependency` từ module này khi khởi động.
# Kiến trúc đa lớp: controller → service → repository → entity.
# Mọi class được scan phải có constructor type-hint đầy đủ.
#
# Package bị loại trừ mặc định (scanner bỏ qua): domain, dto, entity, vo,
# constant, exception.
# ─────────────────────────────────────────────────────────────────────────────

dependency = BindingConfig()

# ── Package scan ──────────────────────────────────────────────────────────────
# Các tầng được DI quản lý. Thêm dần theo từng Phase.
dependency.scan(
    # Starter SQLAlchemy - AsyncEngineProvider, AsyncSessionFactory, SqlAlchemyTransactionManager
    "xime.starters.sqlalchemy",
    # Starter localfs - LocalFileStorage (lưu file qua StorageService, đọc storage.local.root)
    "xime.starters.localfs",
    # Các tầng ứng dụng (đa lớp)
    "app.controller",
    "app.service",
    "app.repository",
    "app.security",
    "app.cache",
)

# ── Protocol → Implementation bindings ───────────────────────────────────────
# Kiến trúc đa lớp phụ thuộc class cụ thể nên hầu như không cần bind.
# Riêng TransactionManager là Protocol của framework → bind sang impl SQLAlchemy.
dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
    # StorageService (Protocol framework) → LocalFileStorage. Đổi sang S3FileStorage khi cần
    # object storage (chỉ sửa dòng bind + cấu hình storage.s3.*, không đụng tầng service).
    StorageService: LocalFileStorage,
    # CacheService (Protocol framework) → InMemoryCacheService (cache catalog trong RAM).
    # Đổi sang RedisCacheService khi deploy nhiều worker (chỉ sửa dòng bind + cấu hình redis.*).
    CacheService: InMemoryCacheService,
})
