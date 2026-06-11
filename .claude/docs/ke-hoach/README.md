# Kế hoạch Tổng thể — Migrate Shop PHP → Python/Xime

Chia thành **10 phase**. Mỗi phase là một mốc độc lập, có nhiều bước với checkbox.
Làm tuần tự: xong phase trước rồi sang phase sau. Cập nhật `[ ]` → `[x]` khi hoàn thành mỗi bước.

## Bản đồ phase

| Phase | Tên | Mục tiêu | File |
|---|---|---|---|
| 0 | Scaffold & môi trường | Cây thư mục, pyproject, kết nối Xime, app chạy rỗng | [phase-0-scaffold.md](phase-0-scaffold.md) |
| 1 | Nền tảng | DB, BaseRepository, exception, error code, JWT middleware, transaction, config | [phase-1-nen-tang.md](phase-1-nen-tang.md) |
| 2 | Entity & migration | 25 SQLAlchemy entity + migration + seed quyền | [phase-2-entity.md](phase-2-entity.md) |
| 3 | Auth | User, token, login/logout/refresh, đổi mật khẩu | [phase-3-auth.md](phase-3-auth.md) |
| 4 | Phân quyền | Permission, group, group_member, user/group permission, AuthorizationService | [phase-4-phan-quyen.md](phase-4-phan-quyen.md) |
| 5 | Catalog | Category, Product, attribute, option | [phase-5-catalog.md](phase-5-catalog.md) |
| 6 | Mua hàng | Cart, Order, OrderDetail, Coupon | [phase-6-mua-hang.md](phase-6-mua-hang.md) |
| 7 | Tương tác & nội dung | Review, Wishlist, Notification, File | [phase-7-tuong-tac.md](phase-7-tuong-tac.md) |
| 8 | Phụ trợ | Search, ListTable, Interaction/Action | [phase-8-phu-tro.md](phase-8-phu-tro.md) |
| 9 | Hoàn thiện | OpenAPI, test, seed admin, rà soát, tài liệu | [phase-9-hoan-thien.md](phase-9-hoan-thien.md) |

## Thứ tự phụ thuộc

```
Phase 0 (scaffold)
   ↓
Phase 1 (nền tảng) ──────────────┐
   ↓                             │ (mọi phase sau đều dựa nền tảng)
Phase 2 (entity) ────────────────┤
   ↓                             │
Phase 3 (auth) ←── cần entity user/token
   ↓
Phase 4 (phân quyền) ←── cần auth (user hiện tại)
   ↓
Phase 5 (catalog) ──┐
Phase 6 (mua hàng) ─┤ ←── cần phân quyền (controller check permission)
Phase 7 (tương tác) ┤      các phase 5–8 khá độc lập với nhau,
Phase 8 (phụ trợ) ──┘      có thể làm song song theo module
   ↓
Phase 9 (hoàn thiện)
```

## Nguyên tắc xuyên suốt

1. **Đa lớp, không Hexagonal** — [`../kien-truc-da-lop.md`](../kien-truc-da-lop.md).
2. **Mỗi module migrate theo lát cắt dọc**: entity → repository → service → dto → controller → test thủ công.
3. **Đối chiếu file PHP gốc** từng bước, giữ nghiệp vụ.
4. **Mỗi controller PHP → 1 controller Python** cùng tên, cùng route path.
5. **Gặp điểm mơ hồ / khác biệt code-schema** (vd `Order`) → ghi chú, hỏi người dùng, không tự quyết logic.

## Checklist tổng (mốc lớn)

- [x] Phase 0 — App Xime chạy rỗng, trả được 1 endpoint health-check ✅ (port 8088, test pass)
- [x] Phase 1 — Nền tảng: DB + transaction, BaseRepository, exception→JSON, current_user ✅ (JWT middleware dời Phase 3; 11/11 test pass)
- [x] Phase 2 — 25 entity + migration (26 bảng) + seed 51 quyền & nhóm admin ✅ (16/16 test pass)
- [x] Phase 3 — Auth: login/logout/refresh/change-password ✅ (JWT HS256, blacklist DB, middleware)
- [x] Phase 4 — Phân quyền chặn/cho phép đúng ✅ (5 repo, 6 service, 5 controller, DTOs; test 4.17 pending)
- [x] Phase 5 — Catalog CRUD đầy đủ ✅ (6 repo, 6 service, DTOs, 2 controller; test 5.9-5.10 pending)
- [x] Phase 6 — Đặt hàng end-to-end ✅ (4 repo, 4 service, DTOs, 3 controller; coupon+test pending)
- [x] Phase 7 — Review/Wishlist/Notification/File ✅ (5 repo, 5 service, DTOs, 4 controller; test 7.12 pending)
- [x] Phase 8 — Search + phụ trợ ✅ (search_service, search_controller, list_table sync, seed list_tables; test 8.7 pending)
- [x] Phase 9 — Test + OpenAPI + bàn giao ✅ (OpenAPI+JWT, seed admin, unit tests, README, .env.example)
