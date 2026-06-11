# Phase 7 — Tương tác & Nội dung (Review, Wishlist, Notification, File)

**Mục tiêu:** Đánh giá, danh sách yêu thích, thông báo, upload/quản lý file.

> Nguồn PHP: `ReviewController/Service`, `WishlistController/Service`, `NotificationController/...`,
> `FileController/Service`. File storage: [`../domain-model.md`](../domain-model.md).

## Bước

### Review
- [x] **7.1** `review_repository.py` — theo product, theo user.
- [x] **7.2** `review_service.py` — tạo, duyệt/bỏ duyệt (is_approved), xóa, liệt kê.
- [x] **7.3** DTO + `review_controller.py`. Quyền: view_reviews, approve_disapprove_review, delete_review.

### Wishlist
- [x] **7.4** `wishlist_repository.py`, `wishlist_service.py` — thêm/xóa/xem theo user.
- [x] **7.5** DTO + `wishlist_controller.py`. Quyền: view/edit/delete_wishlists.

### Notification
- [x] **7.6** `notification_repository.py`, `notification_service.py` — tạo, đánh dấu đã đọc, liệt kê.
- [x] **7.7** DTO + `notification_controller.py`. (Gửi email/SMS thật: chỉ lưu lịch sử như PHP, không
  bắt buộc gửi thật trừ khi yêu cầu.)

### File
- [x] **7.8** `file_repository.py`, `list_table_repository.py`.
- [x] **7.9** `file_service.py` — port cơ chế lưu file:
  - Tên file = 32 ký tự ngẫu nhiên.
  - Đường dẫn `public/data/{2 ký tự đầu}/{2 ký tự tiếp}/{phần còn lại}`.
  - Quan hệ đa hình qua `list_tables` (tên bảng) + id bản ghi.
  - `UPLOAD_DIR` từ config (PHP lấy từ env `UPLOAD_DIR`).
- [x] **7.10** DTO + `file_controller.py` — upload (multipart), tải xuống, xóa. Lỗi file dùng dải E5xxx/E20xxx.
- [x] **7.11** Xử lý multipart trong FastAPI (`UploadFile`) — UploadFile + Form() parameters trong class-based controller; Xime _make_handler giữ nguyên signature nên FastAPI detect đúng.

### Test thủ công
- [ ] **7.12** Tạo review → duyệt → liệt kê. Thêm wishlist. Tạo notification → đánh dấu đã đọc.
  Upload file → kiểm đường dẫn băm đúng + bản ghi files trỏ đúng list_table.

## Đầu ra

4 module nội dung/tương tác hoạt động; file lưu đúng cơ chế băm tên + quan hệ đa hình.

## Rủi ro / cần xác minh

- Upload multipart trong routing layer của Xime (decorator `@post` + `UploadFile`) — kiểm tra hỗ trợ.
- Đường dẫn lưu file vật lý + quyền ghi thư mục.
- `notifications.type` enum.
