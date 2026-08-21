# Thông tin kết nối Cơ sở dữ liệu

> Nguồn thông tin: dự án mẫu `D:\code\xime\Base Platform\data\resources\application.yml`
> (cùng user/host/port). DB `shop` do người dùng tự tạo.
> ✅ Đã kiểm tra kết nối thành công (xem mục "Trạng thái").

## Thông số kết nối

| Thông số | Giá trị |
|---|---|
| DBMS | PostgreSQL 18.3 (x86_64-windows) |
| Host | `localhost` |
| Port | `5432` |
| Database | `shop` |
| Username | `thang` |
| Password | `123456` |
| Driver async (app) | `asyncpg` |

## Connection URL

**Async (dùng trong app / SQLAlchemy async / Alembic env.py):**
```
postgresql+asyncpg://thang:123456@localhost:5432/shop
```

**Sync (nếu cần cho tool đồng bộ):**
```
postgresql+psycopg2://thang:123456@localhost:5432/shop
```

## Cấu hình trong dự án (đề xuất — theo mẫu `data`)

`resources/application.yml`:
```yaml
database:
  url: "postgresql+asyncpg://thang:123456@localhost:5432/shop"
  pool_size: 10
  max_overflow: 20
  echo: false
```

`alembic.ini` (mẫu `data` override URL qua env `DATABASE_URL` trong `migrations/env.py`):
```ini
sqlalchemy.url = postgresql+asyncpg://localhost/shop   # placeholder, env.py đọc DATABASE_URL thật
```

## Lưu ý bảo mật

- ⚠️ Đây là **mật khẩu dev cục bộ** (`123456`). Khi deploy thật thì không để chuỗi thật trong
  file nằm trong git.
- ⚠️ **Xime KHÔNG nội suy `${VAR}` và không override từng khóa bằng biến môi trường.** Env chỉ
  chọn file profile (`XIME_ENV`/`APP_ENV` -> `application-{env}.yml`). Nên cách "đọc từ
  `DATABASE_URL`/`.env`" không hoạt động ở đây; đường đúng là một file profile riêng.
- `application-local.yml` (gitignored) là file profile của máy dev, và nó **chỉ được nạp khi
  `XIME_ENV=local`**. Máy chủ thì ghi đè `application-production.yml` lúc deploy.

## Trạng thái

- ✅ **Kết nối thành công** (kiểm tra qua SQLAlchemy + asyncpg):
  - `SELECT version()` → PostgreSQL 18.3
  - `current_database()` → `shop`
  - `current_user` → `thang`
- Driver đã có sẵn trong môi trường: `asyncpg 0.31.0`, `psycopg2`, `sqlalchemy 2.0.48`, Python 3.14.5.
- DB `shop` hiện **rỗng** (chưa có bảng) — schema sẽ được tạo ở [Phase 2](ke-hoach/phase-2-entity.md) qua migration.
