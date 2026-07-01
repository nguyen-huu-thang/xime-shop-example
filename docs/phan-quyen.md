# Phân quyền

Shop Backend kết hợp **RBAC** (quyền theo nhóm) và **ACL** (cấp quyền cho cá nhân), đánh giá theo
luật **deny-overrides**. Logic nằm ở `AuthorizationService`; tầng controller gọi
`require(...)` / `require_owner_or_permission(...)`.

## Khái niệm

| Khái niệm | Ý nghĩa |
|---|---|
| Permission | Một quyền có tên, vd `view_products`, `create_coupon`, `view_orders` |
| Group | Nhóm gom nhiều quyền; user thuộc nhiều nhóm |
| Grant | Một bản ghi cấp quyền (cho nhóm hoặc cho cá nhân), có `is_active` và `is_denied` |
| Superadmin | Cờ `users.is_superadmin` - bỏ qua mọi kiểm tra (có mọi quyền) |
| Self-service | Thao tác trên dữ liệu của chính mình - chỉ cần đăng nhập, không cần quyền |

## Quy tắc đánh giá (deny-overrides)

Một quyền được coi là **có hiệu lực** với user khi:

1. **Superadmin** -> luôn cho phép.
2. Ngược lại, xét các grant áp dụng cho quyền đó (từ cá nhân và từ các nhóm của user):
   - Nếu có grant **deny** (`is_denied = true`) -> **từ chối** (deny thắng).
   - Nếu có grant **allow** (`is_active = true`, không deny) -> cho phép.
   - Không có grant nào -> dùng `default_value` của quyền.
3. Ưu tiên cấp: **cá nhân > nhóm**; trong cùng cấp, **deny thắng allow**.

> Tất cả quyền seed mặc định `default_value = false`, nên một khách hàng thường (không được cấp grant
> nào) sẽ không có quyền quản trị nào.

## Scope theo nhánh danh mục

Một số quyền sản phẩm/danh mục có `scope_type = "category"`. Grant của chúng kèm `target_id` là một
danh mục; quyền áp cho **cả nhánh con** (subtree) của danh mục đó.

```text
Cấp create_product (target = "Điện tử")  ->  có quyền tạo SP trong Điện tử
                                              và mọi danh mục con của nó
Deny edit_product  (target = "Điện thoại") ->  chặn đúng nhánh con đó (deny thắng)
```

Dùng cho mô hình "mỗi nhân viên phụ trách một mảng hàng". Các quyền scope theo danh mục gồm:
`view_products`, `view_product_details`, `create_product`, `edit_product`, `delete_product`,
`manage_featured_products`, `manage_product_stock`, `edit_category`, `delete_category`.

## Quyền sở hữu (ownership) - chống IDOR

Với tài nguyên thuộc về người dùng (đơn hàng, giỏ, wishlist, đánh giá), endpoint chi tiết dùng
`require_owner_or_permission(user, perm, resource, target_id=id)`:

- **Chủ sở hữu** xem/sửa được tài nguyên của mình.
- Người khác cần **quyền tương ứng** (vd `view_order_details`) mới xem được.
- Không thỏa -> `403` (hoặc `401` nếu chưa đăng nhập).

Ví dụ đã áp: `GET /api/orders/{id}`, `GET /api/wishlist/{id}`, `GET /api/cart/{id}`,
`PUT /api/reviews/{id}` (chỉ chủ sửa).

## Self-service vs quản trị

Phân biệt rõ hai loại thao tác:

| Loại | Yêu cầu | Ví dụ |
|---|---|---|
| Self-service (dữ liệu của chính mình) | Chỉ cần **đăng nhập** | thêm vào giỏ, thêm wishlist, tạo đơn, gửi đánh giá |
| Quản trị (dữ liệu toàn hệ thống / của người khác) | Cần **quyền** tương ứng | `GET /api/cart/all` (`view_carts`), `GET /api/orders/all` (`view_orders`), duyệt đánh giá... |

> Nguyên tắc: thêm vào **giỏ của mình** chỉ cần đăng nhập (item gắn theo `user.id`); còn xem **giỏ của
> mọi người** mới cần quyền `view_carts`.

## Lấy quyền hiệu lực (cho frontend)

`GET /api/me/permissions` trả về **danh sách tên quyền** mà user hiện tại thực sự có (đã áp
deny-overrides). Frontend dùng nó để ẩn/hiện menu quản trị - nhưng backend vẫn là nơi **thực thi**
quyền thật trên từng endpoint.

- Superadmin -> trả về toàn bộ tên quyền.
- Khách hàng thường -> trả về rỗng.

## Seed quyền

`python -m app.seed` tạo:

- Toàn bộ danh mục quyền (~58), `default_value = false`.
- Nhóm `admin` được cấp **tất cả** quyền.
- Tài khoản `admin` (superadmin) - đổi mật khẩu ngay sau khi seed.
- `list_table`, `actions` (cho cá nhân hóa).
