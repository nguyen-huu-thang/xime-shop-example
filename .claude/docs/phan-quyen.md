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

## Thuật toán `check_permission` (port từ PHP)

```
check_permission(user, permission_name, target_id=None, is_user_owned=False) -> bool:
    # 1. Quyền cá nhân
    up = user_permission_service.has_permission(user.id, permission_name, target_id)
    if up < 0:  return False      # bị denied ở cấp user → chặn ngay
    if up > 0:  return True       # được cấp ở cấp user → cho phép
    # up == 0: không có bản ghi user → xét tiếp

    if is_user_owned:  return True  # tài nguyên do chính user sở hữu

    # 2. Quyền nhóm
    groups = group_member_service.find_groups_by_user(user)
    for g in groups:
        if group_permission_service.has_permission(g, permission_name, target_id):
            return True

    # 3. Mặc định của permission
    permission = permission_service.get_permission_by_name(permission_name)
    return permission.default_allow if permission else False
```

> `has_permission` của user trả về **3 trạng thái**: `< 0` (denied), `> 0` (granted), `0` (không có).
> Cần giữ đúng semantics 3 trạng thái này khi port.

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
