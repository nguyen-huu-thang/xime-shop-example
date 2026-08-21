from xime import BindingConfig
from xime.core.transaction.manager import TransactionManager
from xime.starters.cache import CacheService
from xime.starters.jwt import (
    JwtTokenSigner,
    JwtTokenVerifier,
    PyJwtTokenSigner,
    PyJwtTokenVerifier,
)
from xime.starters.localfs import LocalFileStorage
from xime.starters.mail import MailService, SmtpMailService
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
    # Starter mail - SmtpMailService (gửi email qua SMTP, đọc mail.*). Cần mail.smtp.host.
    "xime.starters.mail",
    # Starter jwt - PyJwtTokenSigner / PyJwtTokenVerifier (ký + verify JWT, hỗ trợ kid).
    # KHÔNG gọi configure_jwt(): shop dùng JwtMiddleware tự viết (cần blacklist + nạp user +
    # kiểm type=access), nên chỉ mượn tầng ký/verify chứ không gắn middleware của framework.
    "xime.starters.jwt",
    # Starter lmdb - LmdbEnvironment + StoreCleanupJob (kho liên tiến trình, đọc lmdb.*).
    # Cần khối lmdb.path trong application.yml; framework cố ý KHÔNG đoán đường dẫn vì nhiều
    # service Xime chạy chung một máy sẽ âm thầm trộn bảng của nhau.
    "xime.starters.lmdb",
    # Các tầng ứng dụng (đa lớp)
    "app.controller",
    "app.service",
    "app.repository",
    "app.security",
    "app.cache",
    # Bảng của kho Xime Store (LMDB): bộ đếm hãm nhịp. Subclass phải khai `name` mới vào DI.
    "app.store",
    # Job định kỳ (Xime scheduler) - đăng ký job class để resolver resolve khi cron chạy.
    # Lịch khai báo trong app/config/scheduler.py (framework tự nạp mọi module trong app.config).
    "app.job",
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
    # MailService (Protocol framework) → SmtpMailService (gửi email SMTP, đọc mail.*).
    # SmtpMailService.__init__ cần mail.smtp.host (đã đặt sẵn smtp.gmail.com trong application.yml).
    # Đổi sang backend khác (SendGrid/SES) sau này chỉ sửa dòng bind này.
    MailService: SmtpMailService,
    # JwtTokenSigner / JwtTokenVerifier (Protocol framework) -> impl PyJWT. Bind tường minh vì
    # DI của Xime từ chối đoán khi một Protocol có ứng viên: một chỗ khai, không có mặc định ẩn.
    # Đổi sang HSM/KMS sau này chỉ sửa hai dòng này.
    JwtTokenSigner: PyJwtTokenSigner,
    JwtTokenVerifier: PyJwtTokenVerifier,
})
