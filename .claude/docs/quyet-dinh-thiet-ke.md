# Quyết định Thiết kế (Design Decisions)

> Nơi ghi các quyết định đã chốt cho những điểm mơ hồ giữa code PHP và schema, hoặc những lựa chọn
> kiến trúc. Khi code, **theo các quyết định ở đây** thay vì phân vân lại.

## Bối cảnh & mục đích dự án (quan trọng)

Dự án này là **bản tham chiếu / kiểm thử cho framework Xime**, **KHÔNG** phải sản phẩm thương mại.
Mục tiêu: chứng minh framework chạy được một ứng dụng thật, và làm tài liệu mẫu để người khác tham khảo.

**Hệ quả:**
- **Không** cần migrate dữ liệu người dùng cũ từ PHP → được tự do chọn giải pháp sạch/đơn giản.
- Ưu tiên **rõ ràng, dễ đọc, làm nổi bật cách dùng framework** hơn là tương thích tuyệt đối với bản PHP.
- Khi code PHP và schema mâu thuẫn → chọn phương án hợp lý nhất, ghi lại ở đây, không cần hỏi lại.

---

## QĐ-1: Hash mật khẩu — dùng bcrypt mới, không tương thích PHP

**Vấn đề:** Bản PHP hash mật khẩu bằng cơ chế riêng; nếu migrate user cũ phải verify tương thích.

**Quyết định:** Vì **không migrate user cũ**, dùng **bcrypt qua `passlib`** hoàn toàn mới. Tạo user
test mới bằng chính hệ thống Python. Không cần dò thuật toán hash của PHP.

```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# hash:   pwd_context.hash(plain)
# verify: pwd_context.verify(plain, hashed)
```

**Ảnh hưởng:** Phase 1 (cài `passlib[bcrypt]`), Phase 3 (`UserService` hash/verify), Phase 9 (seed admin
dùng bcrypt). Bỏ mọi ghi chú "xác minh thuật toán hash PHP".

---

## QĐ-2: Entity `Order` — lấy code `Order.php` làm chuẩn, thêm `coupon_id`

**Vấn đề:** `src/Entity/Order.php` và `giải thích cơ sở dữ liệu.txt` khác nhau:

| `Order.php` (code chạy) | Schema (file giải thích) |
|---|---|
| totalAmount, paymentMethod, address, shippingStatus, **paymentStatus (bool)**, shippingFee, **productDiscount**, **shipDiscount**, createdAt, updatedAt, user | total_amount, payment_method, shipping_status, **payment_status (varchar)**, shipping_fee, **discount**, **coupon_id**, created_at, updated_at, user_id |

**Quyết định:** Lấy **`Order.php` (code thực thi) làm nguồn chuẩn**, hợp nhất thêm `coupon_id`:

Bảng `orders` gồm các cột:
- `id` (BigInteger, PK)
- `user_id` (FK → users, not null)
- `total_amount` (Numeric(10,2), not null)
- `payment_method` (String(50), not null)
- `address` (String(255), default '')
- `shipping_status` (String(50), default 'pending')
- `payment_status` (**Boolean**, default False) ← theo `Order.php`
- `shipping_fee` (Numeric(10,2), default 0)
- `product_discount` (Numeric(10,2), default 0) ← theo `Order.php`
- `ship_discount` (Numeric(10,2), default 0) ← theo `Order.php`
- `coupon_id` (FK → coupons, **nullable**) ← bổ sung vì tính năng coupon có tồn tại
- `created_at`, `updated_at` (timestamp)

**Lý do:** code là thứ thực sự chạy; giữ `productDiscount`/`shipDiscount` để sát logic PHP. Thêm
`coupon_id` để liên kết coupon ↔ order (tính năng Phase 6 cần). Bỏ cột `discount` đơn lẻ của schema.

**Ảnh hưởng:** Phase 2 (entity Order), Phase 6 (order service áp coupon vào `coupon_id` + 2 cột discount).

---

## QĐ-3: Bảng `permissions` — cột `default_value` (Boolean)

**Vấn đề:** `AuthorizationService::checkPermission` gọi `$permission->getDefault()` làm fallback, nhưng
file schema (`giải thích cơ sở dữ liệu.txt`) không liệt kê cột này.

**Cập nhật (Phase 2):** Đọc `src/Entity/Permission.php` thấy entity PHP **thực sự có** cột — property
`defaultValue` (boolean, default false) → cột DB **`default_value`**. Vậy không phải "thêm mới" mà là
cột vốn có, chỉ thiếu trong file mô tả schema.

**Quyết định:** Dùng đúng cột **`default_value`** (Boolean, default False, not null) như PHP.
- Tên Python: `default_value` — **không** dùng từ khóa SQL `default`, an toàn.
- Ý nghĩa: nếu user không có quyền cá nhân lẫn quyền nhóm cho permission này, fallback về
  `permission.default_value`.

**Ảnh hưởng:** ✅ Phase 2 (entity `Permission.default_value` — đã làm), Phase 4 (`check_permission`
đọc cột này), Phase 9 (seed có thể set True cho vài quyền "view" công khai nếu muốn; mặc định False).

---

## QĐ-4: Không dùng `relationship()` — service walk quan hệ bằng query tường minh

**Vấn đề:** SQLAlchemy async + `relationship()` lazy-load gây `MissingGreenlet` khi truy cập thuộc tính
quan hệ ngoài ngữ cảnh await (vd `category.parent.name`). `lazy="selectin"` self-ref cũng không eager
qua `session.get()`.

**Quyết định:** Entity **chỉ khai báo cột FK** (`parent_id`, `user_id`, `category_id`...), **không** khai
báo `relationship()`. Service/repository duyệt quan hệ bằng **query tường minh** theo id (vd build
hierarchy danh mục: lặp `get(parent_id)` cho tới khi null).

**Lý do:** (1) An toàn tuyệt đối với async — không lazy-load ngầm. (2) Hợp triết lý đa lớp/explicit.
(3) Khớp cách PHP thực ra cũng gọi query qua repository. Nếu sau cần eager, dùng `selectinload(...)`
**option trong câu select cụ thể**, không gắn mặc định lên entity.

**Ảnh hưởng:** Mọi entity (Phase 2). Service các phase sau tự query quan hệ. Đã kiểm chứng:
`test_insert_and_query_category_hierarchy` walk cha bằng `get(parent_id)` — PASS.

---

## QĐ-5: Kiểu scope của quyền — đặt ở **cột DB** `permissions.scope_type`

**Vấn đề:** Khi nâng cấp phân quyền cho phép scope theo **nhánh category** (cấp quyền ở category cha
phủ cả subtree), cần biết một quyền diễn giải `target_id` theo kiểu nào: "đúng một đối tượng"
(instance-level cũ) hay "cả nhánh category". Lựa chọn: hardcode danh sách quyền category trong code,
hay lưu thành dữ liệu.

**Quyết định:** Lưu thành **cột DB** `permissions.scope_type` (String(20), **nullable**).
- `null` = giữ hành vi cũ: `target_id` khớp **chính xác** đối tượng (instance-level / wildcard theo id).
- `'category'` = `target_id` là id category; khi kiểm tra sẽ dựng **chuỗi tổ tiên** của category resource,
  cấp ở cha áp cho cả subtree; deny ở nhánh con chỉ chặn đúng nhánh đó.

**Lý do:** (1) Đổi/thêm quyền category-scope chỉ cần sửa dữ liệu seed, không sửa code. (2) Tương thích
ngược tuyệt đối: quyền cũ `scope_type=null` chạy y như trước - đó là lý do 70 test cũ không vỡ.
(3) Mở rộng được sang kiểu scope khác về sau (vd `'brand'`) mà không đổi chữ ký hàm.

**Ảnh hưởng:** migration `b2d3f4a5c6e7` (thêm cột); `seed.py` đồng bộ `scope_type='category'` cho ~9
quyền sản phẩm/category; `AuthorizationService._resolve_scope_ids` đọc cột này. Chi tiết:
[`phan-quyen-nang-cap.md`](phan-quyen-nang-cap.md), [`phan-quyen.md`](phan-quyen.md).

---

## QĐ-6: Ownership — chỉ áp cho **người mua**, nhân viên không có ownership

**Vấn đề:** Mọi user (cả nhân viên lẫn người mua) đều là bản ghi `users`. Cần xác định "tài nguyên của
chính mình" áp cho ai: giỏ hàng/wishlist/đơn hàng là của người mua, nhưng nhân viên quản trị thì sao?

**Quyết định:** Ownership (`resource.user_id == user.id`) **chỉ dành cho người mua** với tài nguyên
cá nhân của họ: **cart, wishlist, order**. Nhân viên **không** có khái niệm ownership - quyền của
nhân viên hoàn toàn qua RBAC/ACL + scope category (QĐ-5). Helper:
`AuthorizationService.require_owner_or_permission(user, perm, resource)` - là chủ resource thì cho qua,
không thì mới xét quyền.

**Lý do:** Dự án hiện là **một shop, single-tenant**. Nhân viên thao tác trên hàng hóa của shop theo
quyền được cấp, không "sở hữu" sản phẩm. Gắn ownership cho nhân viên chỉ cần khi lên **sàn nhiều shop**
(mỗi shop sở hữu sản phẩm/đơn của mình) - khi đó thêm `shop_id` và mở rộng `_is_owner`. **Ghi để nhớ
cho tương lai**, chưa làm bây giờ.

**Ảnh hưởng:** Phase 5 nâng cấp phân quyền (gom ownership + vá IDOR `order.detail`/`wishlist.detail`).
Chi tiết: [`phan-quyen-nang-cap.md`](phan-quyen-nang-cap.md).

---

## Ghi chú khác biệt schema phát hiện ở Phase 2 (đã theo code PHP)

Đối chiếu `src/Entity/*.php` vs `giải thích cơ sở dữ liệu.txt`, lấy **code PHP làm chuẩn**:

- **`order_details`** tham chiếu `product_id` (Product), **không** phải `product_option_id`; có thêm
  `name` (snapshot), `attribute` (text), `url`.
- **`wishlist`** tham chiếu `product_id` (Product), không phải product_option.
- **`products`** có thêm `discount_percentage` (int, default 0); `name` dài 300; `is_delete` default
  **False** (file schema ghi true — sai).
- **`list_table`** (số ít, không phải `list_tables`); PK là `id` (String 100), không phải `table_name`.
  `files.list_table_id` FK → `list_table.id`.
- **`notifications`** có thêm `read_at` (nullable); `type` là String(10).
- **`files`** có thêm `target_id` (bigint nullable), `sort`.
- **`actions.name`** dài 20; **`coupons`** không có cột mô tả; **`refresh_tokens`/`blacklist_tokens`**
  PK `id` String(64).
