# Kế hoạch nâng cấp phân quyền (scope theo category + cache + nhóm A)

> Trạng thái: **kế hoạch, chưa code.** Làm theo từng phase nhỏ, **chạy full test (70 pass) + thêm
> test riêng mỗi phase** trước khi sang phase sau. Cập nhật `[ ]` -> `[x]` khi xong.
>
> Bối cảnh thiết kế: [`phan-quyen.md`](phan-quyen.md) (mô hình hiện tại + deny-overrides đã chốt).
> Các vấn đề nền: xem mục "Review bảo mật phân quyền" trong
> [`review-test-2026-06-29.md`](review-test-2026-06-29.md) (mục J-M).

## Quyết định đã chốt (đầu vào của kế hoạch)

1. **Scope = category có phân cấp.** Quyền sản phẩm gắn `target_id` = category; áp cho sản phẩm
   thuộc category đó **và mọi category con** (subtree).
2. **Ownership chỉ cho người mua.** `user` gồm cả nhân viên và người mua. Ownership áp cho tài
   nguyên của người mua: **giỏ hàng, wishlist, đơn hàng** (`resource.user_id == user.id`). Nhân
   viên **không** cần ownership trong phạm vi 1 shop.
   - *Ghi chú tương lai:* nếu lên sàn nhiều shop, nhân viên sẽ cần ownership/scope theo shop. Để dành.
3. **Deny trong subtree khi lọc list: làm chính xác** (cấp nhánh cha nhưng deny nhánh con thì loại
   đúng phần con bị deny).
4. **`scope_type` đặt ở cột DB** trên bảng `permissions` (không phải hằng số trong code).
5. **Một process, chưa Redis.** Cache in-RAM: giữ một snapshot bất biến, **thay nguyên tham chiếu**
   khi đổi (kiểu `AtomicReference`), invalidate khi CRUD dữ liệu nguồn. Không cần khóa vì chạy một
   event loop; chỉ cần không `await` giữa lúc dựng/gán snapshot.
   - Khuôn tham khảo: `D:\code\xime\Base Platform\identity\...\TrustCertificateResolver.java`
     (vật chứa chỉ giữ + invalidate, không tự fetch; bên ngoài kích hoạt nạp lại).
6. **Không cache quyết định cuối** (`check_permission` trả về) xuyên request - rủi ro stale deny.
   Chỉ cache: dữ liệu tham chiếu (permissions, cây category) + memo trong phạm vi một request.

## Lỗ hổng phát hiện khi khảo sát (vá trong Phase 5)

- **IDOR:** `order.detail` và `wishlist.detail` không kiểm ownership -> user bất kỳ đọc được đơn/
  wishlist của người khác qua id. (`cart.detail` đã kiểm đúng.)
- Ownership đang rải rác: vừa inline ở controller, vừa trong service (`update_cart_item(id, user)`).

---

## Phase 1 - Lưới an toàn: test nhất quán quyền code <-> seed (A1) ✅ XONG

**Mục tiêu:** chống tái diễn bug "quyền dùng trong code nhưng quên seed" (đã từng dính
`view_files`/`delete_file`). Không đổi hành vi.

- [x] Viết test quét toàn bộ controller, gom mọi chuỗi quyền truyền vào `require(...)` /
      `check_permission(...)`. -> `test/test_permission_consistency.py` (phân tích AST, không cần DB).
- [x] Assert mọi chuỗi đó tồn tại trong seed (`app.seed.PERMISSIONS`).
- [x] Chạy thử để phát hiện drift hiện có -> **không có drift**; mọi tên quyền đều là literal + đã seed.
- [x] Thêm test phụ chặn tên quyền "động" (không phải hằng chuỗi) để test soi luôn chính xác.

**Kết quả:** 2 test mới pass; full suite **72 passed** (70 cũ + 2 mới). Không đổi hành vi.
**Rủi ro:** rất thấp (chỉ thêm test).

---

## Phase 2 - Superadmin bypass (A2) ✅ XONG

**Mục tiêu:** một cờ cho phép vượt mọi kiểm tra; thôi phải seed đủ 55 quyền cho admin; có "phao"
khi cấu hình quyền lỡ sai.

- [x] Migration: thêm cột `users.is_superadmin` (Boolean, server_default "false") ->
      `migrations/versions/a1c2e3f4b5d6_add_user_is_superadmin.py`, đã `alembic upgrade head`.
- [x] Thêm field vào entity `User`.
- [x] `check_permission`: nếu `user.is_superadmin` -> `return True` ngay đầu (bước 0, trước mọi truy vấn).
- [x] Seed: admin `is_superadmin = true` (cả tạo mới lẫn idempotent cập nhật admin cũ); đã chạy seed.
- [ ] (Tùy chọn, BỎ QUA) JWT claim `isSuperadmin` - chưa cần, để sau nếu FE muốn ẩn/hiện menu.

**Kết quả:** test `test_authz_upgrade.py` (2 test: superadmin short-circuit không đụng deps; user
thường không short-circuit) + full suite **74 passed**.
**Rủi ro:** thấp, additive. Migration đã chạy trên DB `shop` hiện có.

---

## Phase 3 - PermissionRegistry: cache bảng permissions trong RAM ✅ XONG

**Mục tiêu:** bảng `permissions` (~57 dòng, gần như không đổi) đọc từ RAM thay vì DB. Mọi
`check_permission` đều tra permission nên lợi rõ.

- [x] Tạo `PermissionRegistry` ở `app/cache/permission_registry.py` (theo tiền lệ `app/cache/`):
      pure storage, snapshot `dict[name->Permission]` + `dict[id->Permission]` + tuple; thay nguyên
      tham chiếu khi nạp. Khuôn `TrustCertificateResolver` (chỉ giữ + invalidate, không tự fetch).
- [x] `PermissionService` inject registry; `get_permission_by_name / get_all_permissions /
      get_permission_names / get_permission_by_id` đọc qua registry, nạp lazy lần đầu (`_ensure_loaded`).
- [x] Invalidate: `create / update / delete_permission` gọi `registry.invalidate()` **sau commit**.
- [x] Cache thẳng entity `Permission` an toàn vì starter đặt `expire_on_commit=False` và Permission
      không có quan hệ lazy -> caller không phải đổi kiểu trả về.

**Kết quả:** test unit registry (load/get/names/invalidate) + full suite **75 passed**.
**Rủi ro:** thấp. Invalidate đặt sau `async with transaction()` (sau commit), không trước.

---

## Phase 4 - Viết lại get_effective_permissions (L). Cache-per-check (M) HOÃN

**Mục tiêu:** bỏ N+1 ở `get_effective_permissions`.

- [x] Viết lại `get_effective_permissions` theo kiểu **nạp một lần - đánh giá nhiều lần**: load
      `all_perms` (registry) + `groups` + `user_permissions` + `group_permissions` (gộp theo lô),
      rồi chấm tất cả quyền trong bộ nhớ qua helper thuần `_is_effective`. Trước đây 57×(query
      nhóm + grant), nay còn ~3 query + N(số nhóm).
- [x] Thêm `GroupPermissionService.get_records_by_group_ids(...)` (lấy grant nhóm theo lô).
- [x] Superadmin -> trả thẳng toàn bộ tên quyền.
- [x] `_is_effective` giữ **đúng ngữ nghĩa** check_permission(target=None): deny-overrides theo
      cấp, ưu tiên user > group, bỏ qua bản ghi inactive / gắn target cụ thể; fallback default_value.

**HOÃN - cache quyết định/grant theo từng request (M):** framework chỉ tự `clear_security()` cho
slot của nó (identity/credentials); thêm ContextVar riêng sẽ KHÔNG được dọn cuối request -> rủi ro
rò quyết định authz sang request sau (lỗ hổng bảo mật). Bản viết lại đã xử lý phần tốn kém nhất
(get_effective_permissions); các endpoint thường chỉ check 1-2 lần nên lợi của M nhỏ. Để lại tới
khi framework có hook clear request-scoped đáng tin.

**Kết quả:** 7 test helper `_is_effective` (deny-overrides/ưu tiên cấp/default/bỏ inactive-target)
+ full suite **82 passed** (endpoint `get_effective_permissions` của user_controller không đổi hành vi).
**Rủi ro:** trung bình - đã giữ ngữ nghĩa y hệt, có test riêng đối chiếu từng nhánh.

---

## Phase 5 - Gom ownership thành policy + vá IDOR (A3 / K) ✅ XONG

**Mục tiêu:** ownership tập trung một chỗ, bỏ logic `item.user_id == user.id` rải rác; vá IDOR.

- [x] Thêm `AuthorizationService._is_owner(user, resource)` + `require_owner_or_permission(user,
      perm, resource, target_id=None)`: chủ sở hữu (`resource.user_id == user.id`) luôn qua, người
      khác phải có quyền; ném E2025 nếu chưa đăng nhập, E2021 nếu thiếu quyền.
- [x] Tài nguyên người mua có ownership: cart, wishlist, order (đều có cột `user_id`).
- [x] **Vá IDOR:** `order.detail` (trước đây KHÔNG kiểm gì, kể cả require_login) và `wishlist.detail`
      nay `require_login` + `require_owner_or_permission` (view_order_details / view_wishlists).
- [x] `cart.detail` gom logic owner-or-permission rải rác về helper (hành vi giữ nguyên).
- [x] Giữ chữ ký cũ `require(user, perm, target_id=..., is_user_owned=...)` song song (user-self-edit
      vẫn dùng) - không phá controller khác.

**Kết quả:** 4 unit test ownership + 1 integration IDOR (`test_wishlist_detail_idor_blocked_for_non_owner`:
user thường -> 403 E2021, chủ sở hữu -> 200) + full suite **87 passed**.
**Lưu ý tương lai:** lên sàn nhiều shop thì nhân viên cũng cần ownership/scope theo shop (xem quyết định 2).
**Rủi ro:** trung bình - đụng 3 controller; superadmin (admin test) vẫn xem được mọi đơn/wishlist.

---

## Phase 6 - CategoryTreeCache (nền cho scope) ✅ XONG

**Mục tiêu:** duyệt tổ tiên (lúc check) và mở rộng con (lúc lọc list) bằng RAM, không query cây
mỗi lần.

- [x] Tạo `app/cache/category_tree_cache.py`: snapshot `id->parent_id` + `parent_id->[children]`;
      `ancestor_ids(id) -> list[int]` (self + tổ tiên, phòng chu trình), `descendant_ids(id) -> set[int]`
      (self + con cháu). Pure storage (khuôn `TrustCertificateResolver`).
- [x] `CategoryService` inject cache; `_ensure_tree_loaded` nạp lazy từ `find_all`; public
      `get_ancestor_ids` / `get_descendant_ids`.
- [x] Invalidate: `create / update / delete_category` gọi `invalidate()` **sau commit**.

**Kết quả:** 3 unit test (ancestor/descendant/invalidate trên cây mẫu) + full suite **90 passed**.
**Rủi ro:** thấp. CategoryService không phụ thuộc ngược authz (authz sẽ gọi CategoryService ở Phase 7).

---

## Phase 7 - Mô hình scope: scope_type + khớp theo tập + check resource-aware ✅ XONG

**Mục tiêu:** quyền sản phẩm áp theo nhánh category.

- [x] Migration `b2d3f4a5c6e7`: thêm `permissions.scope_type` (nullable). Quyền cũ `null` giữ nguyên.
- [x] Seed: 9 quyền `scope_type='category'` (view_products, view_product_details, create_product,
      edit_product, delete_product, manage_featured_products, manage_product_stock, edit_category,
      delete_category) + sync idempotent cho DB đã seed.
- [x] `has_permission` (user + group) nhận **tập** `scope_ids`: "áp dụng" = `target_id is None` HOẶC
      `target_id in scope_ids`. Deny-overrides giữ nguyên. 2 controller /check truyền `{target_id}`.
- [x] `check_permission` + `require` thêm `resource`; resolve `perm` một lần, dựng `scope_ids` qua
      `_resolve_scope_ids` (quyền category -> `get_ancestor_ids(resource.category_id|target_id)`;
      quyền thường -> `{target_id}`). Inject `CategoryService`.
- [x] Wiring controller: product edit/delete/attribute nạp product -> `resource=product`; product
      create -> `target_id=categoryId`; category delete -> `target_id=id` (category edit đã có sẵn).

**Kết quả:** 4 unit (`_resolve_category_id` / `_resolve_scope_ids` các nhánh) + 1 integration
(`test_category_scoped_edit_product_subtree`: cấp edit_product ở category CHA -> sửa được sản phẩm
nhánh CON 200, nhánh khác 403) + full suite **95 passed**. Quyền global (target None) vẫn áp mọi nơi
nên admin/grant cũ không đổi hành vi.
**Rủi ro:** đã đổi semantics `has_permission`; mọi nhánh có test, admin superadmin bypass nên các
luồng cũ an toàn.

---

## Phase 8 - Lọc danh sách theo scope + deny chính xác trong subtree (nặng nhất, làm cuối)

**Mục tiêu:** nhân viên chỉ thấy hàng thuộc mảng (nhánh category) mình phụ trách.

### Phần lõi ✅ XONG

- [x] `AuthorizationService.allowed_category_scope(user, perm)` -> `None` (= TẤT CẢ, cho superadmin)
      hoặc **tập category id** được phép. Tính bằng cách duyệt mọi category, mỗi category xét bằng
      `_decide_in_memory` với `scope_ids = chuỗi tổ tiên` -> **deny ở nhánh con chỉ chặn đúng nhánh
      đó (chính xác)**, không cần phép trừ tập thủ công.
- [x] Refactor `_is_effective` thành trường hợp đặc biệt của `_decide_in_memory` (scope rỗng) - hết trùng.
- [x] `CategoryTreeCache.all_ids()` + `CategoryService.get_all_category_ids()`.
- [x] Test: `_decide_in_memory` (deny subtree chính xác: cấp P, deny C -> P được, C+cháu bị chặn,
      nhánh khác default) + `allowed_category_scope` (cây 10->20->30 + 40, cấp 10 deny 20 -> {10}) +
      superadmin -> None. Full suite **99 passed**.

### Phần wiring ✅ XONG (quyết định: thêm endpoint admin riêng)

Storefront công khai (`GET /api/products`, count, by-category, detail) **giữ nguyên** cho khách mua
hàng. Thêm endpoint quản trị riêng có lọc theo mảng nhân viên:

- [x] Repo: `find_paginated_in_categories(category_ids, page, limit)` + `count_active_in_categories(...)`.
- [x] Service: `ProductService.get_managed_product_dtos(allowed, page, limit)` +
      `count_managed_products(allowed)` (allowed None = không lọc).
- [x] Controller: `GET /api/products/managed` + `/managed/count` (cần đăng nhập): gọi
      `allowed_category_scope(user, "view_products")` rồi lọc. Đặt trước route `/{id}` để khỏi bị nuốt.
- [x] Test integration `test_managed_product_list_filtered_by_scope`: nhân viên cấp view_products ở
      category cha -> thấy sản phẩm nhánh con, KHÔNG thấy nhánh khác; superadmin gọi được không lọc.

**Kết quả:** full suite **100 passed**.
**Rủi ro:** đã khoanh đúng chỗ - storefront khách hàng không đổi; chỉ endpoint /managed mới lọc.

---

## Sau khi xong tất cả

- [ ] Cập nhật [`phan-quyen.md`](phan-quyen.md): bổ sung mục scope/category + superadmin + ownership.
- [ ] Ghi quyết định "scope_type ở DB", "ownership chỉ người mua + note multi-shop" vào
      [`quyet-dinh-thiet-ke.md`](quyet-dinh-thiet-ke.md).
- [ ] Cập nhật mục J-M trong [`review-test-2026-06-29.md`](review-test-2026-06-29.md) thành đã xử lý.
