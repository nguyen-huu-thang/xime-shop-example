# Phase 4 — Phân quyền (Authorization)

**Mục tiêu:** Permission, group, group_member, user/group permission + `AuthorizationService` hoạt động;
controller các phase sau dùng được `authz.require(...)`.

> Tham chiếu: [`../phan-quyen.md`](../phan-quyen.md). Nguồn PHP: `AuthorizationService.php`,
> `UserPermissionService.php`, `GroupPermissionService.php`, `GroupMemberService.php`,
> `PermissionService.php`, các controller tương ứng.

## Bước

### Repository
- [x] **4.1** `permission_repository.py` — `find_by_name`, CRUD.
- [x] **4.2** `group_repository.py` — CRUD.
- [x] **4.3** `group_member_repository.py` — `find_groups_by_user`, thêm/xóa thành viên.
- [x] **4.4** `user_permission_repository.py` — truy vấn theo (user_id, permission_name, target_id).
- [x] **4.5** `group_permission_repository.py` — truy vấn theo (group, permission_name, target_id).

### Service
- [x] **4.6** `permission_service.py` — `get_permission_by_name`, CRUD.
- [x] **4.7** `group_service.py` — CRUD nhóm.
- [x] **4.8** `group_member_service.py` — `find_groups_by_user`, quản lý thành viên.
- [x] **4.9** `user_permission_service.py` — `has_permission(user_id, name, target_id) -> int`
  (**3 trạng thái**: <0 denied, >0 granted, 0 không có). Giữ đúng semantics.
- [x] **4.10** `group_permission_service.py` — `has_permission(group, name, target_id) -> bool`.
- [x] **4.11** `authorization_service.py` — `check_permission(...)` (thuật toán ở
  [`../phan-quyen.md`](../phan-quyen.md)) + helper `require(...)` raise E2025/E2021.

### DTO + Controller
- [x] **4.12** DTO request/response cho permission/group/member.
- [x] **4.13** `permissions_controller.py` (port `PermissionsController`).
- [x] **4.14** `user_permission_controller.py`.
- [x] **4.15** `group_controller.py`, `group_member_controller.py`, `group_permission_controller.py`.
- [x] **4.16** Áp `authz.require(...)` đúng tên quyền cho từng endpoint (đối chiếu chuỗi permission
  trong controller PHP, vd `manage_group_permissions`).

### Test thủ công
- [ ] **4.17** User không quyền → bị E2021. User có quyền (cá nhân hoặc qua nhóm admin) → cho phép.
  Test `is_denied` chặn dù có quyền nơi khác. Test `target_id` (full vs chi tiết).

## Đầu ra

`AuthorizationService.require(...)` dùng được ở mọi controller; phân quyền user + group + denied + target
hoạt động đúng như PHP.

## Rủi ro / cần xác minh

- Semantics 3 trạng thái của `user_permission has_permission` (đọc kỹ `UserPermissionService.php`).
- ✅ Cột fallback `permissions.default_allow` — **đã chốt (QĐ-3)**, đọc trong `check_permission`.
- Quy ước `is_user_owned` (tham số thứ 4) dùng ở đâu trong controller PHP.
