# Mô hình Phân quyền (Authorization)

> Nguồn: `src/Service/AuthorizationService.php`, `UserPermissionService.php`,
> `GroupPermissionService.php`, `giải thích cơ sở dữ liệu.txt`.

## Tổng quan

Phân quyền 2 cấp: **quyền cá nhân (user_permissions)** + **quyền nhóm (group_permissions)**.
Mỗi bản ghi quyền gồm: `permission_id`, `target_id`, `is_active`, `is_denied`.

| Cột | Ý nghĩa |
|---|---|
| `target_id` | Phân quyền chi tiết. `null` = full quyền đó. Giá trị cụ thể = chỉ áp dụng cho đối tượng đó (vd id của group). |
| `is_active` | Quyền đã bật chưa. Admin có thể setup sẵn nhưng chưa kích hoạt. |
| `is_denied` | Từ chối quyền. **Denied thắng** — dù được cấp ở nơi khác vẫn bị chặn. |

## Thuật toán `check_permission` (deny-overrides trong từng cấp)

> ⚠️ **Cập nhật 2026-06-29 (review bảo mật):** thuật toán cũ thoát sớm theo bản ghi/nhóm đầu
> tiên khớp, nên một `allow` có thể che mất một `deny` tùy thứ tự DB trả về - phá vỡ nguyên
> tắc "deny thắng". Đã sửa sang **deny-overrides trong từng cấp**: quét HẾT bản ghi/nhóm áp
> dụng được; có deny là chặn, không thì mới xét allow. Vẫn giữ **ưu tiên cấp user > group**
> (quyền cấp user cho phép vẫn override group - để admin gỡ riêng cho 1 người).

```
check_permission(user, permission_name, target_id=None, is_user_owned=False) -> bool:
    # 1. Quyền cá nhân (deny thắng trong cấp này)
    up = user_permission_service.has_permission(user.id, permission_name, target_id)
    if up < 0:  return False      # bị denied ở cấp user → chặn ngay
    if up > 0:  return True       # được cấp ở cấp user → cho phép (override group)
    # up == 0: không có bản ghi user → xét tiếp

    if is_user_owned:  return True  # tài nguyên do chính user sở hữu

    # 2. Quyền nhóm (deny-overrides trên TẤT CẢ nhóm, không thoát sớm)
    groups = group_member_service.find_groups_by_user(user)
    saw_group_allow = False
    for g in groups:
        gp = group_permission_service.has_permission(g, permission_name, target_id)
        if gp < 0:  return False           # bất kỳ nhóm nào deny → chặn ngay
        if gp > 0:  saw_group_allow = True  # nhớ lại, KHÔNG return sớm
    if saw_group_allow:  return True

    # 3. Mặc định của permission
    permission = permission_service.get_permission_by_name(permission_name)
    return permission.default_allow if permission else False
```

> `has_permission` (user và group) trả về **3 trạng thái**: `< 0` (denied), `> 0` (granted),
> `0` (không có). Bản thân nó cũng theo **deny-overrides**: quét hết bản ghi áp dụng được
> (global `target_id is None` HOẶC khớp `target_id`); gặp deny là `-1`, hết vòng có allow là
> `1`, còn lại `0`. Không return theo bản ghi đầu tiên.

> ✅ **Đã chốt chính sách (QĐ phân quyền, 2026-06-29): ưu tiên theo cấp user > group, trong mỗi
> cấp deny thắng.** Nghĩa là:
>
> - Trong cấp user: có deny là chặn, không thì xét allow (deny-overrides nội bộ cấp user).
> - Trong cấp group: bất kỳ nhóm nào deny là chặn, không thì xét allow (deny-overrides nội bộ cấp group).
> - Giữa hai cấp: **user thắng group** - user được cấp riêng (allow, không có deny ở cấp user) sẽ
>   override deny ở cấp nhóm. Chủ ý để admin gỡ/cấp riêng cho một người bất kể nhóm.
>
> Đã loại phương án "deny tuyệt đối toàn cục" (deny ở bất kỳ đâu là chặn kể cả khi user được cấp
> riêng) vì mất khả năng admin gỡ riêng cho một người. Nếu sau này đổi ý, chỉ cần sửa bước 1 của
> `check_permission`: quét deny mọi cấp trước rồi mới xét allow.

> ✅ **Đã chốt (QĐ-3):** bảng `permissions` có cột `default_allow` (Boolean, default False) làm fallback.
> Không đặt tên cột `default` (từ khóa SQL). Xem [`quyet-dinh-thiet-ke.md`](quyet-dinh-thiet-ke.md#qđ-3-bảng-permissions--thêm-cột-default-boolean).

## Đề xuất cho Python

Giữ `AuthorizationService.check_permission(...)` y hệt logic trên. Bổ sung helper để giảm lặp:

```python
# service/authorization_service.py
class AuthorizationService:
    def __init__(self, user_permission_service, group_member_service,
                 group_permission_service, permission_service): ...

    async def check_permission(self, user, permission_name, target_id=None,
                               is_user_owned=False) -> bool:
        ...  # logic như trên

    async def require(self, user, permission_name, target_id=None, is_user_owned=False) -> None:
        # Raise nếu thiếu quyền — dùng trong controller cho gọn
        if user is None:
            raise AppException("E2025")          # cần đăng nhập
        if not await self.check_permission(user, permission_name, target_id, is_user_owned):
            raise AppException("E2021")          # không được phép
```

## Nâng cấp đã triển khai (2026-06-29) — xem [`phan-quyen-nang-cap.md`](phan-quyen-nang-cap.md)

Đã bổ sung (8 phase, full suite 100 pass):

- **Superadmin bypass:** cột `users.is_superadmin`; `check_permission` trả True ngay ở bước 0.
- **Cache RAM (một tiến trình):** `PermissionRegistry` (bảng permissions) + `CategoryTreeCache`
  (cây category), pure-storage + invalidate khi CRUD. `get_effective_permissions` viết lại
  load-once (hết N+1).
- **Ownership tập trung:** `require_owner_or_permission(user, perm, resource)` cho tài nguyên người
  mua (cart/wishlist/order = `resource.user_id == user.id`); đã vá IDOR `order.detail`/`wishlist.detail`.
- **Scope theo nhánh category:** cột `permissions.scope_type` (`'category'`). `has_permission` khớp
  theo **tập** `scope_ids`; quyền category-scope dùng chuỗi tổ tiên của category resource ->
  cấp ở category cha áp cho cả subtree; deny ở nhánh con chỉ chặn đúng nhánh đó.
- **Lọc danh sách quản trị:** `allowed_category_scope(user, perm)` + endpoint `GET /api/products/managed`
  (nhân viên chỉ thấy mảng mình; superadmin thấy tất cả). Storefront công khai `GET /api/products` giữ nguyên.

> Lưu ý: instance-level cũ vẫn còn (quyền `scope_type=null` khớp đúng `target_id`); category-scope
> là tổng quát hóa. Ownership cho nhân viên (đa shop) để dành tương lai.

## Danh sách quyền (~55 quyền — seed ban đầu)

Nhóm theo chức năng (đầy đủ trong `giải thích cơ sở dữ liệu.txt`, dòng ~218):

- **User**: view_users, view_user_details, create_user, edit_user, delete_user, activate_deactivate_user, manage_user_permissions
- **Group**: view_groups, view_group_details, create_group, edit_group, delete_group, manage_group_members, manage_group_permissions
- **Permission**: view_permissions, create_permission, edit_permission, delete_permission
- **Product**: view_products, view_product_details, create_product, edit_product, delete_product, manage_featured_products, manage_product_stock
- **Category**: view_categories, create_category, edit_category, delete_category
- **Cart**: view_carts, edit_carts, delete_carts
- **Wishlist**: view_wishlists, edit_wishlists, delete_wishlists
- **Coupon**: view_coupons, create_coupon, edit_coupon, delete_coupon, activate_deactivate_coupon
- **Order**: view_orders, view_order_details, update_shipping_status, update_payment_status, delete_order
- **Review**: view_reviews, approve_disapprove_review, delete_review
- **System**: access_admin_dashboard, manage_system_settings, view_system_logs

→ Seed bằng script khởi tạo (tương đương `SetupInitialCommand.php`), tạo cùng nhóm `admin` full quyền.
