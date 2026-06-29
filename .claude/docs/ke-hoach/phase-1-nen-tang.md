# Phase 1 — Nền tảng

**Mục tiêu:** Hạ tầng dùng chung cho mọi module: DB, BaseRepository, transaction, exception/error code,
context người dùng. Sau phase này, mỗi module chỉ còn việc CRUD theo khuôn.

> ⚠️ **Điều chỉnh phạm vi:** JWT middleware đầy đủ (verify + blacklist + load user) **dời sang Phase 3**
> vì cần UserService + BlacklistService + entity User (chưa có ở Phase 1). Phase 1 chỉ làm hạ tầng
> `current_user()` qua SecurityContext của framework.

> Tham chiếu: [`../error-code-system.md`](../error-code-system.md), [`../auth-jwt.md`](../auth-jwt.md),
> [`../../rules/repository-pattern.md`](../../rules/repository-pattern.md),
> [`../../rules/transaction.md`](../../rules/transaction.md).

## Bước

### Cơ sở dữ liệu & SQLAlchemy
- [x] **1.1** Đọc `xime.starters.sqlalchemy`. ✅ Pattern: scan `"xime.starters.sqlalchemy"` →
  `AsyncEngineProvider` (đọc `database.url` từ application.yml), `AsyncSessionFactory` (repo gọi
  `.current()` để lấy session — **chỉ** trong transaction), `SqlAlchemyTransactionManager`.
- [x] **1.2** DB url đã có trong `resources/application.yml` (PostgreSQL `shop`).
- [x] **1.3** Tạo `app/entity/base.py` — re-export `Base`, `TimestampMixin` của starter (chung metadata).
- [x] **1.4** Bật starter (`dependency.scan("xime.starters.sqlalchemy")` + bind `TransactionManager`).
  Test `SELECT 1` qua transaction — **PASS**.

### Repository nền
- [x] **1.5** Tạo `app/repository/base_repository.py` (`find`, `find_all`, `count`, `save`, `delete`) —
  inject `AsyncSessionFactory`, property `session` = `self._sessions.current()`.
- [x] **1.6** `dependency.scan("app.repository")` đã khai báo.

### Exception & Error code
- [x] **1.7** `app/exception/error_code.py` — **copy đầy đủ** bảng mã từ `ErrorCode.php` (dict `ERROR_CODES`
  + dataclass `ErrorDef` + `get_error()` fallback E0000).
- [x] **1.8** `app/exception/app_exception.py` — `AppException(error_key, custom_message?)`.
- [x] **1.9** `app/exception/handler.py` + `app/shop_web_adapter.py` — `AppException` → JSON
  `{errorKey, code, message}` đúng http_status. Subclass `WebAdapter` (lúc đó framework chưa có hook public).
  > Cập nhật 2026-06-29: đã gỡ `app/shop_web_adapter.py`, chuyển sang `configure_exception_handlers(...)`
  > trong `app/config/web.py`; issue-002 đã đóng (file đã xóa). Xem
  > [`go-web-adapter-dung-configure.md`](../go-web-adapter-dung-configure.md).
- [x] **1.10** Handler lỗi validation Pydantic → JSON `E10711` (kèm `details`).

### Security (current_user)
- [x] **1.11** Dùng **SecurityContext của framework** (`xime.core.security`: `identity`/`credentials`/
  `authenticate`/`clear_security`) thay vì tự nhét key. Tự dọn cuối request bởi `RequestContextMiddleware`.
- [x] **1.12** `app/security/current_user.py` — `current_user()`, `current_jwt()`, `require_login()`
  (raise E2025), `set_current_user()`.
- [~] **1.13** JWT middleware (verify + blacklist + load user) → **dời Phase 3**.

### Kết
- [x] **1.14** Test `test/test_phase1_foundation.py` — 9 test (DB, exception→JSON, validation, unit
  AppException/error_code/current_user) — **PASSED**. App boot sạch qua `ShopWebAdapter`.

## Đầu ra

✅ DB kết nối + transaction hoạt động. `BaseRepository` sẵn sàng. `AppException` → JSON chuẩn.
`current_user()` qua SecurityContext framework. 11/11 test pass.

## Ghi chú đã chốt

- **Session chỉ khả dụng trong `async with transaction()`** — kể cả đọc. Repo gọi `self.session`
  (= `AsyncSessionFactory.current()`), raise nếu ngoài transaction.
- **Bind `TransactionManager → SqlAlchemyTransactionManager`** trong `dependency.py`. Lưu ý:
  `app.get(TransactionManager)` (Protocol) KHÔNG resolve trực tiếp — binding chỉ áp dụng khi inject
  vào constructor. Test lấy class cụ thể `SqlAlchemyTransactionManager`.
- **Exception handler:** ~~subclass `WebAdapter` → override `build_app`~~ - nay dùng
  `configure_exception_handlers({...})` trong `app/config/web.py` (framework đã có hook public).
  Xem [`go-web-adapter-dung-configure.md`](../go-web-adapter-dung-configure.md).
- **JWT config** (secret, issuer, audience, TTL) → thêm ở Phase 3 cùng middleware.
