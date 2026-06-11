# Phase 2 — Entity & Migration

**Mục tiêu:** 25 SQLAlchemy entity ánh xạ 1-1 từ `src/Entity/*.php` + schema CSDL, sinh migration,
seed danh sách quyền.

> Tham chiếu: [`../domain-model.md`](../domain-model.md) (schema + nghiệp vụ),
> [`../mapping-php-python.md`](../mapping-php-python.md) (Doctrine → SQLAlchemy).

## Nguyên tắc map entity

- Đối chiếu **cả** `src/Entity/X.php` **và** `giải thích cơ sở dữ liệu.txt` (có khác biệt nhỏ, vd `Order`).
- Dùng `Mapped[...]` + `mapped_column(...)`. Quan hệ dùng `relationship()` + `ForeignKey`.
- ID `BigInteger` autoincrement; token tables `String(64)`; `list_tables` PK `table_name`.
- Timestamp dùng `TimestampMixin`.
- `entity/__init__.py` export `Base` + mọi entity (để Alembic autogenerate thấy hết).

## Bước (theo cụm, mỗi cụm 1 commit logic)

### Cụm A — User & phân quyền
- [ ] **2.1** `entity/user.py` — `users`
- [ ] **2.2** `entity/permission.py` — `permissions` + cột `default_allow` (Boolean, default False) — QĐ-3
- [ ] **2.3** `entity/group.py` — `groups`
- [ ] **2.4** `entity/group_member.py` — `group_members` (unique user_id+group_id)
- [ ] **2.5** `entity/user_permission.py` — `user_permissions` (target_id, is_active, is_denied)
- [ ] **2.6** `entity/group_permission.py` — `group_permissions`

### Cụm B — Catalog
- [ ] **2.7** `entity/category.py` — `categories` (self-ref parent_id)
- [ ] **2.8** `entity/product.py` — `products` (is_active, is_delete, popularity, location_address)
- [ ] **2.9** `entity/product_attribute.py` — `product_attributes`
- [ ] **2.10** `entity/product_attribute_value.py` — `product_attribute_values`
- [ ] **2.11** `entity/product_option.py` — `product_options` (price, stock)
- [ ] **2.12** `entity/product_option_value.py` — `product_option_values` (bảng nối)

### Cụm C — Mua hàng
- [ ] **2.13** `entity/cart.py` — `cart`
- [ ] **2.14** `entity/wishlist.py` — `wishlist`
- [ ] **2.15** `entity/coupon.py` — `coupons`
- [ ] **2.16** `entity/order.py` — `orders` theo **QĐ-2**: `product_discount`, `ship_discount`, `address`,
  `payment_status` (Boolean), `shipping_fee`, `total_amount`, `payment_method`, `shipping_status`,
  `coupon_id` (nullable FK), timestamps. Xem [`../quyet-dinh-thiet-ke.md`](../quyet-dinh-thiet-ke.md).
- [ ] **2.17** `entity/order_detail.py` — `order_details`

### Cụm D — Tương tác & nội dung
- [ ] **2.18** `entity/review.py` — `reviews`
- [ ] **2.19** `entity/notification.py` — `notifications` (type enum email/sms/push)
- [ ] **2.20** `entity/interaction.py` — `interactions`
- [ ] **2.21** `entity/action.py` — `actions`

### Cụm E — Hạ tầng
- [ ] **2.22** `entity/file.py` — `files` (quan hệ đa hình qua list_tables)
- [ ] **2.23** `entity/list_table.py` — `list_tables` (PK table_name)
- [ ] **2.24** `entity/refresh_token.py` — `refresh_tokens` (id String(64), expires_at)
- [ ] **2.25** `entity/blacklist_token.py` — `blacklist_tokens`

> ✅ **Tất cả 25 entity (2.1–2.25) đã viết xong** trong `app/entity/`, dùng `Mapped`/`mapped_column`,
> kế thừa `Base`/`TimestampMixin` của starter. Chỉ FK column, **không** `relationship()` (QĐ-4).
> Khác biệt schema so với file mô tả → theo code PHP (xem [`../quyet-dinh-thiet-ke.md`](../quyet-dinh-thiet-ke.md)).

### Migration & seed
- [x] **2.26** Alembic cấu hình (`alembic.ini`, `migrations/env.py` async đọc url từ application.yml,
  `import app.entity` để có đủ metadata). Autogenerate → `migrations/versions/7d62679560d0_*.py`.
- [x] **2.27** 25 bảng detect đầy đủ; đối chiếu cột theo code PHP.
- [x] **2.28** `alembic upgrade head` → 26 bảng trong DB (25 + alembic_version).
- [x] **2.29** Script seed `app/seed.py` (51 quyền + nhóm `admin` full quyền), **idempotent**,
  dùng DI framework (TransactionManager + AsyncSessionFactory). Chạy: `python -m app.seed`.
  Admin **user** (có mật khẩu) dời Phase 9 (cần UserService).

## Đầu ra

✅ Schema DB tạo đầy đủ (26 bảng) từ migration. 51 quyền + nhóm admin đã seed.
Test `test/test_phase2_entities.py` (5 test: metadata, Order QĐ-2, permission default_value, hierarchy,
seed) — **PASS**. Tổng 16/16 test.

## Ghi chú đã chốt

- **QĐ-2** (Order), **QĐ-3** (`default_value` — cột PHP thật, không phải `default_allow`),
  **QĐ-4** (không relationship). Khác biệt schema khác xem [`../quyet-dinh-thiet-ke.md`](../quyet-dinh-thiet-ke.md).
- `notifications.type` → `String(10)` (đơn giản, validate ở service/DTO).
- **Cách chạy migration:** `python -m alembic upgrade head`; tạo mới: `python -m alembic revision --autogenerate -m "..."`.
