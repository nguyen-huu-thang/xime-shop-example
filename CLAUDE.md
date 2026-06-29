# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mục tiêu dự án

Migrate shop backend từ **PHP/Symfony** (`D:\code\PHP\shop-backend`) sang **Python**, dùng framework
**Xime** (`D:\code\xime\xime framework`). Giữ **kiến trúc đa lớp** của bản gốc (KHÔNG dùng Hexagonal
như Xime khuyến nghị).

## 📂 Toàn bộ thiết kế & kế hoạch nằm trong `.claude/`

> **Bắt đầu phiên làm việc: đọc [`.claude/CLAUDE.md`](.claude/CLAUDE.md)** — đây là điểm vào của mọi
> tài liệu (kiến trúc, kế hoạch theo phase, quy tắc code, mapping PHP→Python).

Bản đồ nhanh:

| Cần gì | Đọc |
|---|---|
| Điểm vào / mục lục | [`.claude/CLAUDE.md`](.claude/CLAUDE.md) |
| **Kiến trúc đa lớp + lý do không Hexagonal** | [`.claude/docs/kien-truc-da-lop.md`](.claude/docs/kien-truc-da-lop.md) |
| Cây thư mục Python | [`.claude/docs/cay-thu-muc.md`](.claude/docs/cay-thu-muc.md) |
| **Kế hoạch migrate (10 phase)** | [`.claude/docs/ke-hoach/README.md`](.claude/docs/ke-hoach/README.md) |
| Quy tắc code | [`.claude/rules/coding-da-lop.md`](.claude/rules/coding-da-lop.md) |
| Domain model (schema CSDL) | [`.claude/docs/domain-model.md`](.claude/docs/domain-model.md) |
| Mapping PHP → Python | [`.claude/docs/mapping-php-python.md`](.claude/docs/mapping-php-python.md) |
| Phân quyền / Error code / JWT | [`.claude/docs/phan-quyen.md`](.claude/docs/phan-quyen.md), [`error-code-system.md`](.claude/docs/error-code-system.md), [`auth-jwt.md`](.claude/docs/auth-jwt.md) |

## Nguồn & đích

| | Đường dẫn |
|---|---|
| Nguồn PHP | `D:\code\PHP\shop-backend\src\` |
| Đích Python | `d:\code\PYTHON\xime\shop\app\` |
| Framework Xime | `D:\code\xime\xime framework\` |
| App mẫu dùng Xime | `D:\code\xime\Base Platform\data\app\` |

## Cách chạy (khi đã có code)

```bash
python app/main.py        # hoặc: python -m app.main
```

Framework tự thêm `./app` vào `sys.path`.

## Trạng thái hiện tại

**Đã hoàn thiện migrate (Phase 0-9)** và đang ở **pha tối ưu**: app chạy được, đầy đủ
controller/service/repository/entity, test pass. Các cải tiến đã làm sau migrate:

- Auth: refresh token chuyển sang **httpOnly cookie path-scoped** (`/api/refresh-token`),
  access token trả body; `/refresh-token` xoay refresh token (rotation).
- `JwtMiddleware` chuyển sang **pure-ASGI** (sửa rò identity giữa request).
- `order_service` + `product_service`: gộp transaction, bỏ N+1; thêm `OrderResponse` DTO.
- **Storage starter** (localfs) cho upload + endpoint stream `/media/{key}` (HTTP Range).
- **Cache** catalog (InMemoryCacheService, đổi sang Redis được) + invalidation.
- **Dashboard** thống kê: `GET /api/dashboard/stats`.
- Vá bug: thiếu quyền `view_files`/`delete_file` trong seed.
- **Gỡ `ShopWebAdapter` tự viết** -> dùng API `configure_cors` / `configure_middleware` /
  `configure_exception_handlers` của Xime trong `app/config/web.py`; `main.py` chỉ còn `WebAdapter()`.
  Chi tiết wiring web layer: [`.claude/docs/go-web-adapter-dung-configure.md`](.claude/docs/go-web-adapter-dung-configure.md).


## framework issues

nếu framework có bất kì vấn đề gì hãy ghi lại vào .claude\framework-issues
đọc .claude\framework-issues\README.md