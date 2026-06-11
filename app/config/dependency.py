from xime import BindingConfig
from xime.core.transaction.manager import TransactionManager
from xime.starters.sqlalchemy import SqlAlchemyTransactionManager

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
    # Starter SQLAlchemy — AsyncEngineProvider, AsyncSessionFactory, SqlAlchemyTransactionManager
    "xime.starters.sqlalchemy",
    # Các tầng ứng dụng (đa lớp)
    "app.controller",
    "app.service",
    "app.repository",
    "app.security",
)

# ── Protocol → Implementation bindings ───────────────────────────────────────
# Kiến trúc đa lớp phụ thuộc class cụ thể nên hầu như không cần bind.
# Riêng TransactionManager là Protocol của framework → bind sang impl SQLAlchemy.
dependency.bind({
    TransactionManager: SqlAlchemyTransactionManager,
})
