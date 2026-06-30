# Review + bổ sung test backend shop (2026-06-29)

> Phiên làm việc: viết test còn thiếu, chạy với DB thật (DB dev/test, không có dữ liệu giá trị),
> và review code tìm logic bất hợp lý. File này ghi lại bug đã sửa + các vấn đề còn tồn (chờ
> quyết định) + khoảng trống test còn lại.

## Tóm tắt

- Baseline trước phiên: **50 test pass** (`test_integration_db.py` và các file phase).
- Đã thêm **2 file test mới**:
  - `test/test_extra_coverage.py` (16 test) - phủ các controller trước đây chưa có test:
    coupon, user (register/me/admin CRUD/bảo vệ admin), group CRUD, group-member,
    group-permission, user-permission, security (change/verify password), product phụ
    (count/by-category/attribute/find-option), phân quyền (user thường -> 403), user bị khóa.
  - `test/test_edge_cases.py` (4 test) - thăm dò đường biên + chống tái xuất hiện (regression).
- Sau khi sửa bug: **70 test pass** (`python -m pytest test/`).

## Bug đã phát hiện và ĐÃ SỬA

### 1. Coupon dùng SAI mã lỗi (message gây hiểu nhầm) - [đã sửa]

`coupon_service.py` / `coupon_controller.py` dùng mã lỗi của module khác:

| Chỗ dùng cũ | Mã cũ | Message mã cũ (sai ngữ cảnh) | Đã đổi sang |
|---|---|---|---|
| create thiếu code/discount | `E10700` | "Id người dùng là bắt buộc" | `E10402` "Phiếu giảm giá không hợp lệ" + message rõ |
| not-found (detail/update/delete) | `E10701` | "Tên file là bắt buộc" | `E10400` "Phiếu giảm giá không tồn tại" (404) |

Đúng họ mã coupon là `E10400` (không tồn tại, 404) và `E10402` (không hợp lệ, 400).
Client trước đây nhận "Tên file là bắt buộc" khi coupon không tồn tại - rất khó hiểu.

### 2. Tạo coupon trùng `code` -> HTTP 500 (lộ lỗi DB) - [đã sửa]

`coupons.code` có ràng buộc `UNIQUE` (`coupons_code_key`). `create_coupon` không kiểm tra trùng
trước khi insert -> `asyncpg.UniqueViolationError` -> `IntegrityError` không bắt -> **500**.
Sửa: kiểm tra `find_by_code(code)` trong transaction, trùng thì raise `AppException("E10402",
"Mã giảm giá đã tồn tại")`.

> Còn lại 1 khe hở đua (race) rất hẹp nếu 2 request tạo cùng code đồng thời: cả hai qua được
> kiểm tra rồi 1 cái fail ở commit. Ràng buộc UNIQUE vẫn đảm bảo không tạo trùng dữ liệu; chỉ là
> request thua vẫn nhận 500. Với app single-tenant nhỏ, chấp nhận được. Nếu muốn triệt để: thêm
> handler chung cho `IntegrityError` (xem mục I bên dưới).

### 3. Tạo coupon với ngày sai định dạng -> HTTP 500 - [đã sửa]

`datetime.fromisoformat("khong-phai-ngay")` raise `ValueError` không bắt -> **500**.
Sửa: thêm helper `_parse_date()` bọc `try/except` -> raise `AppException("E10402",
"Ngày không đúng định dạng ISO")`. Áp dụng cho cả create và update.

> Cách tốt hơn (nâng cấp, chưa làm): đổi `start_date`/`end_date` trong `CouponCreateRequest`
> /`CouponUpdateRequest` từ `str` sang `datetime` để Pydantic validate ngay ở tầng DTO (trả 422
> chuẩn), service khỏi parse. Đổi nhẹ contract nhưng sạch hơn.

### 4. Assign permission 2 lần tạo bản ghi TRÙNG + crash dây chuyền - [đã sửa]

`group_permission_service.assign_permissions` và `user_permission_service.assign_permissions`
insert thẳng, không kiểm tra entry `(group/user, permission, target)` đã tồn tại. Gọi assign cù
quyền 2 lần -> 2 bản ghi trùng (test thấy `group-permissions = [19, 19]`).

Hậu quả dây chuyền: sau khi có bản ghi trùng, `update_permission`/`delete_permissions` gọi
`find_by_group_and_permission` (dùng `scalar_one_or_none`) -> **`MultipleResultsFound` (500)** và
không xóa/sửa được nữa (kẹt dữ liệu).

Sửa:
- Thêm repo `find_by_group_permission_target` / `find_by_user_permission_target` khớp đúng
  `(group/user, permission, target_id)`, dùng `.first()` để không vỡ nếu lỡ đã có bản trùng cũ.
- `assign_permissions` thành **idempotent**: có entry thì cập nhật, chưa có thì tạo mới. Vẫn giữ
  được khả năng 1 quyền có nhiều `target_id` khác nhau.

## Vấn đề CÒN TỒN (chưa sửa - cần bạn quyết định)

### E. Đăng nhập KHÔNG kiểm tra `is_active` -> user bị khóa vẫn login được

`UserService.verify_user_password` không kiểm `user.is_active` (dù docstring ghi "active user").
Test xác nhận: user bị khóa gọi `/api/login` vẫn **200 + accessToken**. May là `JwtMiddleware`
kiểm `is_active` khi nạp user nên token đó bị từ chối (401) ở request sau. Tức là token "chết yểu"
nhưng login vẫn báo thành công -> trải nghiệm sai, dễ gây nhầm cho frontend.

- **Khuyến nghị:** ở `verify_user_password`, sau khi verify mật khẩu, nếu `not user.is_active`
  thì raise lỗi rõ ràng (ví dụ thêm mã "tài khoản đã bị khóa", hoặc tái dùng `E1004`).
- **Lý do chưa tự sửa:** đây là thay đổi hành vi + cần chọn mã lỗi/message -> hỏi bạn trước.
  Cần đối chiếu bản PHP gốc xem nó chặn ở đâu.

### F. `cart_service.create_cart_item` tách nhiều transaction -> TOCTOU tồn kho

Hàm đọc `option` ở 1 transaction, đọc `existing` ở transaction khác, kiểm `option.stock` (giá trị
đã cũ - đọc ngoài transaction ghi), rồi ghi ở transaction thứ 3. Hai request mua song song có thể
cùng qua kiểm tra rồi đẩy tồn kho âm. (Đối chiếu: `order_service.create_order` làm ĐÚNG - gói tất
cả trong **một** transaction.)

- **Khuyến nghị:** gộp đọc-kiểm-ghi vào 1 transaction, đọc lại `option.stock` ngay trong đó
  (có thể `SELECT ... FOR UPDATE` nếu cần khóa hàng). Cùng pattern double-fetch này trước đây cũng
  có ở `coupon_service.update/delete` - đã gộp lại trong phiên này.

### G. Endpoint `/check` nhận `body: dict` thô thay vì DTO đã có sẵn

`group_permission_controller.has_permission` và `user_permission_controller.has_permission` khai
báo `body: dict`, tự `body.get(...)`. Đã có sẵn `CheckPermissionRequest` trong
`permission_request.py` nhưng không dùng -> mất validation + tài liệu OpenAPI kém. Tương tự
`product_controller.find_option(body: dict)`.

- **Khuyến nghị:** dùng DTO Pydantic cho các endpoint này (đổi nhỏ, an toàn).

### H. `AuthorizationService.get_effective_permissions` N+1

Duyệt toàn bộ tên quyền và gọi `check_permission` cho từng quyền (mỗi lần nhiều truy vấn). Đã có
ghi chú trong code; gọi sau đăng nhập nên tần suất thấp, tạm chấp nhận. Có thể tối ưu bằng cách
nạp 1 lần toàn bộ user/group permission rồi tính trong bộ nhớ.

### I. Thiếu handler chung cho `IntegrityError`

App map `AppException` + `RequestValidationError` (xem `app/config/web.py`). Mọi lỗi DB còn sót
(unique/FK) sẽ thành 500 thô. Sau khi vá coupon (mục 2) thì hết điểm lộ đã biết, nhưng để phòng
xa nên cân nhắc thêm `configure_exception_handlers({IntegrityError: ...})` map về 409/400 chuẩn.

## Khoảng trống test còn lại (chưa viết, không khẩn cấp)

- `order_controller`: cập nhật địa chỉ đơn (`PUT /api/orders/{id}`), danh sách/đếm đơn, đơn theo user.
- `cart_controller`: cập nhật số lượng item (`PUT`), xóa item trực tiếp (mới test gián tiếp qua order).
- `coupon_service.get_coupon_by_code` (chưa có endpoint gọi tới).
- `review`/`wishlist`/`notification`: đã có happy-path (7.12); chưa test nhánh lỗi/validation.

## Framework Xime

Không phát hiện bug framework trong phiên này. Các lỗi 500 đều ở tầng app (không bắt
ValueError/IntegrityError, sai mã lỗi). Cơ chế transaction của framework rollback đúng khi có
exception. Không tạo mới `framework-issues`.

## Cách chạy lại

```bash
cd shop/backend
python -m app.seed                 # đảm bảo có admin + permissions
python -m pytest test/ -q          # 70 passed
python -m pytest test/test_edge_cases.py -v -s   # xem riêng nhóm regression
```

## Dọn dẹp code thừa sau migrate (2026-06-29, phiên sau)

- **Bỏ `app/entity/base.py`:** trước đây re-export `Base`/`TimestampMixin`. Đã đổi 28 file
  (25 entity + `entity/__init__.py` + `migrations/env.py` + `test/test_phase2_entities.py`) sang
  import thẳng `from xime.starters.sqlalchemy import ...` và xóa file. Test vẫn 70 pass.
- **Xóa `app/common/`** (+ `constant/`, `util/`): chỉ chứa `__init__.py` rỗng, chưa từng dùng.
- **Giữ `app/validator/`** (rỗng): để dành cho validator cần truy vấn DB sau này.
- **Giữ `app/entity/action.py` + `interaction.py`:** entity mồ côi (PHP có service dùng, chưa port).
  Là nền cho tính năng **chấm điểm/cá nhân hóa người dùng** sẽ làm sau - KHÔNG xóa.

### Việc cần xem kỹ sau (chưa làm)

- **`order_service.find_order_by_id` (dòng 99) là method thừa:** không controller/test nào gọi;
  trùng vai trò với `get_order_by_id` (bản có dùng, raise E10500 khi không thấy). Cần rà lại có
  định dùng không rồi gỡ, hoặc gộp về một method.
- **`BaseRepository` bị DI tạo 1 singleton thừa:** vô hại. Đã ghi đề xuất framework cung cấp sẵn
  CRUD base (loại bỏ singleton này) tại `framework-issues/issue-003-base-repository-crud-trong-starter.md`.

### Đã refactor: 4 service phân loại sản phẩm (chọn cách 2 - delegate)

Trước đây logic phân loại (thuộc tính/option/biến thể) bị **trùng 2 bản**: vừa inline trong
`product_service.py`, vừa có 4 service `product_attribute*/product_option*` đầy đủ nhưng không ai gọi.
Đã refactor cho `ProductService` ủy thác lại cho 4 service (giống mô hình PHP, hết trùng lặp):

- 4 sub-service đổi thành **collaborator transaction-agnostic** (bỏ `TransactionManager`, bỏ
  `async with self._transaction()`), thêm `find_by_id`. Lý do bắt buộc: `SqlAlchemyTransactionManager`
  tạo **session mới mỗi lần gọi `transaction()` (không reentrant)** - nếu sub-service tự mở transaction
  khi được `ProductService` gọi thì thành commit lẻ, mất tính atomic của tạo/sửa sản phẩm + biến thể.
- `ProductService` mở **một** transaction cho mỗi thao tác rồi gọi method sub-service bên trong;
  bỏ 4 repo attr/option khỏi constructor, chỉ giữ `product_repo` + `category_repo` + 4 sub-service.
- Test: 70 pass (đã phủ `create product + attribute`, `set attribute/option`, `find-option`).

## Review bảo mật phân quyền (2026-06-29, phiên sau)

Rà toàn chuỗi: `controller` -> `AuthorizationService` -> `user/group_permission_service` ->
`group_member_service` + kiểm tra enforcement ở mọi controller. Mô hình hiện tại là **lai
RBAC (group = role) + ACL (user_permissions) + object-scoping (`target_id`) + explicit deny
(`is_denied`) + default fallback** - mạnh hơn shop nhỏ thông thường, hướng đúng.

**Điểm tốt giữ nguyên:** enforcement phủ kín ở controller (không dính OWASP "Broken Function
Level Authorization"); JWT chắc (bắt buộc claim `jti/exp/iss/aud`, check `type==access`,
blacklist, re-load user + check `is_active` mỗi request); refresh rotation + blacklist khi logout.

### ĐÃ SỬA: deny-overrides không được đảm bảo toàn cục (lỗ hổng leo thang quyền)

Tài liệu [`phan-quyen.md`](phan-quyen.md) ghi "deny thắng" nhưng code cũ **thoát sớm theo bản
ghi/nhóm đầu tiên khớp**, nên một `allow` có thể che mất một `deny` tùy thứ tự DB trả về.

- Kịch bản: user thuộc 2 nhóm, nhóm A cấp `delete_order`, nhóm B deny `delete_order`. Nếu A
  được duyệt trước -> `return True`, deny của B không bao giờ được xét -> by-pass deny.
- Lỗi cùng loại trong `has_permission` (user và group): bản ghi global-allow `target_id is None`
  che mất bản ghi deny cụ thể hơn.

Đã sửa sang **deny-overrides trong từng cấp** (giữ ưu tiên cấp user > group):
- `user_permission_service.has_permission` + `group_permission_service.has_permission`: quét HẾT
  bản ghi áp dụng được (`target_id is None` HOẶC khớp target); gặp deny là `-1`, hết vòng có
  allow là `1`, còn lại `0`. Không return theo bản ghi đầu tiên.
- `authorization_service.check_permission` (vòng nhóm): bất kỳ nhóm nào deny -> `False` ngay;
  chỉ `True` nếu có nhóm cấp và không nhóm nào deny (không thoát sớm).
- Test: 70 pass. Tài liệu `phan-quyen.md` đã cập nhật khớp logic mới.

### CÒN TỒN -> phần lớn ĐÃ XỬ LÝ trong đợt nâng cấp phân quyền (xem [`phan-quyen-nang-cap.md`](phan-quyen-nang-cap.md))

- **J. Quyền cấp user override deny cấp nhóm (chính sách) - ĐÃ CHỐT:** phương án (b) "ưu tiên cấp
  user > group, trong mỗi cấp deny thắng" (đã là hành vi sau khi sửa #1). Chốt trong `phan-quyen.md`.
- **K. Ownership rải rác / `is_user_owned` - ĐÃ XỬ LÝ (Phase 5):** thêm
  `AuthorizationService.require_owner_or_permission` + `_is_owner`; vá IDOR `order.detail` /
  `wishlist.detail`; gom logic owner-or-permission. (Ownership cho người mua: cart/wishlist/order.)
- **L. `get_effective_permissions` N+1 - ĐÃ XỬ LÝ (Phase 4):** viết lại load-once-evaluate-many
  (`_decide_in_memory`); thêm `PermissionRegistry` (Phase 3) cache bảng permissions trong RAM.
- **M. Cache quyết định theo request - HOÃN có chủ đích:** framework chưa có hook clear request-scoped
  đáng tin (ContextVar riêng sẽ rò sang request sau -> rủi ro bảo mật). Phần nặng (effective perms)
  đã xử lý ở L. Chờ framework hỗ trợ. Xem Phase 4 trong `phan-quyen-nang-cap.md`.

## Tối ưu N+1 Product/Variant (2026-06-30, phiên sau)

Luồng đọc sản phẩm dựng N+1: `_to_dto` query thuộc tính/option theo từng sản phẩm, lặp qua cả
trang (~70 query/trang với 10 sp x 2 thuộc tính x 3 variant); `GET /api/products` lại không cache.
`find_product_option_by_json` cũng N+1 (mỗi option 1 query option_values).

Đã xử lý (full suite **103 passed**, chi tiết [`toi-uu-product-variant.md`](toi-uu-product-variant.md)):

- **Index + UNIQUE (migration `c3e4a5b6d7f8`):** index 5 cột FK của nhóm product/variant (Postgres
  không tự tạo index FK) + UNIQUE `(product_id, name)` và `(option_id, attribute_value_id)` chặn rác.
- **Batch query gỡ N+1:** thêm `find_by_*_ids` ở 4 repo/sub-service; `ProductService._to_dtos`
  nạp tất cả bằng 4 query `WHERE ... IN (...)` rồi ráp DTO trong RAM (`_build_attributes`,
  `_calc_price_stock`). List M sản phẩm: từ `M x (N+1)` xuống **~4 query cố định**. DTO không đổi.
- **`find_product_option_by_json`:** batch option_values theo `option_ids`, so set trong RAM:
  từ `1 + N_opt` xuống **2 query**.
- **Test mới `test_product_dto_batch.py`:** khóa chống N+1 (mỗi batch method gọi đúng 1 lần dù nhiều
  sản phẩm) + kiểm tra giá trị DTO mọi nhánh tính giá/tồn.
- **Hoãn:** Phase 6 (cache trang list) - list đã ~4 query nên ưu tiên thấp. Backlog: thêm
  `sku`/`barcode`/ảnh/`position` cho variant; tách "default option" khỏi bảng variant thật.

## Cá nhân hóa người dùng - không AI (2026-06-30, phiên sau)

Dựng cá nhân hóa từ 3 entity mồ côi (Action/Interaction/Wishlist) làm kho sự kiện có trọng số.
Phase 1-5 xong (full suite **122 passed**), chi tiết [`ca-nhan-hoa-nguoi-dung.md`](ca-nhan-hoa-nguoi-dung.md):

- **Nền:** `ActionRegistry` (cache RAM bảng điểm), seed 6 actions + quyền `manage_recommendations`.
- **Ghi tín hiệu:** `InteractionService.record()` fault-tolerant + throttle tín hiệu yếu; gắn ở
  view/add_to_cart/wishlist/purchase. FK interactions ON DELETE CASCADE (migration `d4f5a6b7c8e9`).
- **Affinity:** bảng materialized `user_category_affinity` decay-on-write (half-life 30 ngày), nối vào record().
- **Gợi ý:** `recently-viewed` / `trending` (cache, window 14 ngày) / `for-you` (affinity, cold-start -> trending).
- **Mua cùng:** `product_cooccurrence` từ đồng mua (order_details); `GET /products/{id}/related`.
- **Scheduler:** tự dựng lại co-occurrence hằng ngày 03:00 qua **Xime scheduler** (`apscheduler`
  4.0.0a6 đã có; package `app.job` đã scan). **Gate bỏ qua khi pytest** (AsyncScheduler rò giữa các
  TestApplication event loop) - chỉ chạy ở prod; đã smoke-test start/stop sạch. Manual:
  `POST .../admin/rebuild-cooccurrence`.
- **CÒN TỒN:** lệnh sửa chữa rebuild-affinity (Phase 6 tùy chọn) chưa làm.
