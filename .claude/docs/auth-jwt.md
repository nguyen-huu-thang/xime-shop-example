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

### Dùng `xime.starters.jwt`? - ĐÃ CHỐT (2026-08-21): hướng B lai A

Starter JWT của Xime tự gắn middleware khi gọi `configure_jwt()`. Logic ở đây đặc thù (kiểm tra
blacklist trong DB, 2 loại token liên kết qua `refresh_id`, nạp user vào context), nên:

- **Middleware vẫn tự viết** (`security/jwt_middleware.py`, pure-ASGI). **KHÔNG gọi
  `configure_jwt()`** - gọi là gắn thêm middleware của framework, và `public_paths` của nó so
  khớp **chính xác từng đường dẫn** chứ không theo tiền tố, trong khi shop có nhiều endpoint
  công khai (catalog, `/media/{key}`).
- **Lõi ký/verify dùng starter**: `JwtTokenSigner` / `JwtTokenVerifier` inject qua DI (bind
  trong `config/dependency.py`), kèm `ShopJwtKeyProvider` implement Protocol `JwtKeyProvider`.

Ba thứ lấy được so với gọi thẳng pyjwt:

| | |
|---|---|
| **`kid` trong header token** | Xoay khóa được mà không đăng xuất toàn bộ người dùng: bên verify giữ nhiều khóa cùng lúc và chọn theo từng token |
| **`leeway`** | Dung sai đồng hồ cho `exp`/`nbf`/`iat`. Thiếu nó thì hai máy lệch vài giây sinh 401 chập chờn - loại lỗi không tái hiện được trên máy dev |
| **`algorithms` là danh sách trắng** | Áp TRƯỚC khi kiểm chữ ký; token không tự chọn được thuật toán yếu hơn |

Quy trình xoay khóa và các khóa cấu hình mới: [`nang-cap-xime-0.8.md`](nang-cap-xime-0.8.md#21-jwt-ký-verify-đi-qua-starter-của-framework-và-token-có-kid).

⚠ `validate_token` ép `require=["jti","exp","iss","aud"]`: PyJWT chỉ kiểm `exp` KHI claim tồn
tại, nên token không mang `exp` sẽ không bao giờ hết hạn.

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

### Cấu hình (resources/application.yml)

⚠ Xime **không** nội suy `${VAR}` và **không** override từng khóa bằng biến môi trường: env chỉ
chọn file profile (`XIME_ENV`/`APP_ENV` -> `application-{env}.yml`). Nên không có `JWT_SECRET`
dạng biến môi trường - mọi thứ nằm trong YAML.

```yaml
jwt:
  secret: "..."            # khóa ĐANG ký
  key_id: "k1"             # trở thành header `kid` của token mới
  algorithm: "HS256"       # cũng là danh sách trắng lúc verify
  leeway: 30               # giây dung sai đồng hồ
  previous_keys: []        # khóa cũ, CHỈ verify, dùng trong cửa sổ xoay khóa
  accept_unkeyed: true     # chấp nhận token cũ chưa có `kid` tới khi chúng hết hạn
  issuer: "https://scime.click"
  audience: "https://shop.scime.click"
  access_ttl: 3600
  refresh_ttl: 5184000
```
