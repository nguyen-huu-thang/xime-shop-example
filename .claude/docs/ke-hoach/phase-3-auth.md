# Phase 3 — Auth (Xác thực)

**Mục tiêu:** Đăng nhập/đăng xuất/refresh token chạy thật, hoàn thiện JWT middleware (load user + blacklist).

> Tham chiếu: [`../auth-jwt.md`](../auth-jwt.md). Nguồn PHP: `SecurityController.php`,
> `AuthenticationService.php`, `RefreshTokenService.php`, `BlacklistTokenService.php`, `UserService.php`.

## Lát cắt cần migrate

Repository → Service → DTO → Controller cho cụm auth.

## Bước

### Repository
- [x] **3.1** `repository/user_repository.py` — `find_by_username`, `find_by_email`, `find(id)`.
- [x] **3.2** `repository/refresh_token_repository.py` — lưu/tra/xóa theo id, dọn token hết hạn.
- [x] **3.3** `repository/blacklist_token_repository.py` — thêm id, kiểm tra tồn tại, dọn hết hạn.

### Service
- [x] **3.4** `service/user_service.py` (phần auth): `get_user_by_id`, `verify_user_password`,
  `change_user_password`, `verify_password`. Hash bằng **bcrypt qua `passlib`** (QĐ-1) — không cần dò PHP.
- [x] **3.5** `service/refresh_token_service.py` — tạo/lưu/kiểm tra refresh token id.
- [x] **3.6** `service/blacklist_token_service.py` — `is_blacklisted`, thêm khi logout.
- [x] **3.7** `service/authentication_service.py`:
  - `create_token(user, type, refresh_id=None)` — JWT HS256, claims jti/uid/type.
  - `extract_token_id`, `validate_token`.
  - `refresh_access_token`, `refresh_refresh_token`, `logout`.

### Hoàn thiện middleware
- [x] **3.8** `security/jwt_middleware.py` — JwtMiddleware (BaseHTTPMiddleware) mới hoàn toàn:
  verify → check blacklist → type=access → load user → is_active → set context. Lỗi → E1023.
  Đăng ký qua `configure_middleware(JwtMiddleware, ...Inject(...))` trong `app/config/web.py`
  (trước đây qua `ShopWebAdapter.build_app()`; xem [`go-web-adapter-dung-configure.md`](../go-web-adapter-dung-configure.md)).

### DTO
- [x] **3.9** `dto/request/auth_request.py`: `LoginRequest`, `RefreshTokenRequest`, `ChangePasswordRequest`,
  `VerifyPasswordRequest`.
- [x] **3.10** `dto/response/token_response.py`: `TokenResponse`, `AccessTokenResponse`,
  `RefreshTokenResponse`, `MessageResponse`.

### Controller
- [x] **3.11** `controller/security_controller.py` — port `SecurityController` đủ 6 endpoint:
  `/api/login` (POST), `/api/refresh-token` (POST), `/api/logout` (GET), `/api/change-password` (POST),
  `/api/verify-password` (POST), `/api/refresh-refresh-token` (POST). Giữ nguyên path + method + mã lỗi.
- [x] **3.12** Scan đã khai báo từ Phase 1 (`service`, `repository`, `security`, `controller`) — không cần thêm.
  JWT config thêm vào `resources/application.yml`.

### Test thủ công
- [ ] **3.13** Tạo 1 user test (qua seed/script). Đăng nhập → nhận token. Gọi endpoint cần auth với
  token → OK. Logout → token vào blacklist → gọi lại bị chặn. Refresh token → access mới.

## Đầu ra

Luồng auth end-to-end hoạt động; middleware chặn đúng theo blacklist/type/active.

## Ghi chú triển khai

- Claims JWT giữ đúng như PHP: `jti`, `uid`, `username`, `email`, `isActive`, `type`, `refreshId`, `reuseCount`.
- TTL: access 3600s (1h), refresh 5184000s (60 ngày) — lấy từ PHP, đọc qua `RuntimeConfig.get("jwt.*")`.
- `expire_on_commit=False` trong Xime starter — entity sau transaction vẫn accessible.
- Middleware được thêm AFTER `super().build_app()` → là lớp ngoài cùng (chạy đầu tiên).
