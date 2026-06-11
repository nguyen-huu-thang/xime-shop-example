# Xác thực JWT

> Nguồn: `src/Service/AuthenticationService.php`, `src/EventListener/JwtAuthenticatorListener.php`,
> `src/Service/RefreshTokenService.php`, `BlacklistTokenService.php`, `SecurityController.php`.

## Mô hình token (PHP)

- **Thuật toán**: HS256 (HMAC SHA-256), khóa từ `JWT_SECRET` (env).
- **Issuer / Audience**: `JWT_ISSUER`, `JWT_AUDIENCE` (env).
- **Hai loại token**:
  - **Refresh token** — tạo trước, dài hạn. Chỉ lưu **id** (claim `jti`) vào bảng `refresh_tokens` + hạn.
  - **Access token** — ngắn hạn, mang `refresh_id` (liên kết tới refresh token cha).
- **Claims chính**: `jti` (token id), `uid` (user id), `type` (`access`|`refresh`).

## Luồng login (`SecurityController::login`)

```
1. Nếu đã đăng nhập → throw S0000
2. verify_user_password(username, password) → user
3. refresh_token = create_token(user, 'refresh')
4. refresh_id = extract_token_id(refresh_token)
5. access_token = create_token(user, 'access', refresh_id)
6. return { accessToken, refreshToken }
```

## Luồng xác thực mỗi request (`JwtAuthenticatorListener`)

```
1. Không có header Authorization → bỏ qua (request ẩn danh, cho phép tiếp)
2. Header không bắt đầu 'Bearer ' → 401
3. jwt = phần sau 'Bearer '
4. validate_token(jwt)  → parsed
5. token_id = claim 'jti'; nếu blacklist_token_service.is_blacklisted(token_id) → E2050
6. uid = claim 'uid'; type = claim 'type'
7. type != 'access' → E2050
8. user = user_service.get_user_by_id(uid)
9. !user || !user.is_active → E1004
10. set user + jwt vào context request
   (lỗi bất kỳ trong try → E1023)
```

> **Quan trọng:** không có header = **không** chặn. Việc chặn (yêu cầu đăng nhập) do **controller**
> quyết định qua `current_user()` + phân quyền. Middleware chỉ *xác thực nếu có token*.

## Các endpoint auth khác (`SecurityController`)

| Endpoint | Method | Mô tả |
|---|---|---|
| `/api/login` | POST | đăng nhập |
| `/api/refresh-token` | POST | cấp lại access token từ refresh token |
| `/api/logout` | GET | thêm access token id vào blacklist |
| `/api/change-password` | POST | đổi mật khẩu (cần đăng nhập) |
| `/api/verify-password` | POST | xác thực lại mật khẩu |
| `/api/refresh-refresh-token` | POST | cấp lại refresh token mới |

## Thiết kế Python

### Dùng `xime.starters.jwt`?

Starter JWT của Xime tự động middleware. **Nhưng** logic ở đây đặc thù (kiểm tra blacklist trong DB,
2 loại token liên kết qua `refresh_id`, set user vào context). Hai hướng:

- **A. Tự viết middleware** trong `security/jwt_middleware.py` — sát PHP nhất, kiểm soát hoàn toàn.
  Khuyến nghị nếu starter JWT không cho hook kiểm tra blacklist.
- **B. Dùng starter JWT** cho phần verify chữ ký, tự thêm tầng kiểm tra blacklist + load user.

→ **Quyết định ở Phase 1/Phase 3** sau khi đọc kỹ `xime.starters.jwt`. Mặc định nghiêng hướng A.

### `current_user()` — thay `$request->attributes->get('user')`

Xime có `core/context` (request-scoped qua `ContextVar`). Middleware set user vào context, controller
lấy ra:

```python
# security/current_user.py
def current_user() -> User | None:
    return request_context.get("user")
```

### Mật khẩu — đã chốt (QĐ-1)

- **Không** migrate user cũ → dùng **bcrypt qua `passlib`** mới hoàn toàn, tạo user test mới. Không cần
  dò thuật toán hash của PHP.
- Chi tiết: [`quyet-dinh-thiet-ke.md`](quyet-dinh-thiet-ke.md#qđ-1-hash-mật-khẩu--dùng-bcrypt-mới-không-tương-thích-php).

### Biến môi trường cần (resources/application.yml hoặc .env)

```
JWT_SECRET=...
JWT_ISSUER=https://scime.click
JWT_AUDIENCE=https://shop.scime.click
JWT_ACCESS_TTL=...    # thời gian sống access token
JWT_REFRESH_TTL=...   # thời gian sống refresh token
```
