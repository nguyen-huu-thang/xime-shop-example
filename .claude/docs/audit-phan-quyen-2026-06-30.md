# Rà soát & vá phân quyền (2026-06-30)

> Rà soát toàn bộ controller tìm endpoint thiếu kiểm tra quyền, vá các lỗ hổng đang mở.
> Liên quan: [`phan-quyen.md`](phan-quyen.md). Trạng thái: ĐÃ VÁ + test regression (151 test pass).

## Lỗ hổng đã vá

### 1. `search_controller.py` - thiếu auth (đã vá)
Trước đây mọi endpoint công khai. Lưu ý: các method service hiện trả `[]` (chưa cài logic thực)
nên **chưa rò rỉ dữ liệu thật**, nhưng để hở sẽ lộ ngay khi cài logic. Đã thêm auth theo dữ liệu:

| Endpoint | Trước | Sau |
|---|---|---|
| `GET /api/search/users` | công khai | `require_login` + quyền `view_users` |
| `GET /api/search/groups` | công khai | `require_login` + quyền `view_groups` |
| `GET /api/search/cart` | công khai | `require_login` (dữ liệu giỏ của user) |
| `GET /api/search/orders` | công khai | `require_login` (đơn của user) |
| `GET /api/search/all` | công khai | **giữ công khai** (tìm chung, trả []) |
| `GET /api/search/products`, `/products/category` | công khai | **giữ công khai** (tìm sản phẩm) |

`SearchController` nay inject thêm `AuthorizationService`.

### 2. `review_controller.py` - IDOR + giả mạo + lộ review chưa duyệt (đã vá)
- **`POST /` (create):** trước lấy `userId` từ body -> giả mạo người viết. Đã **bỏ `userId` khỏi
  `ReviewCreateRequest`**; controller gán `data["userId"] = user.id` theo user đăng nhập.
- **`PUT /{id}` (update):** trước chỉ `require_login()` -> ai cũng sửa review người khác (IDOR). Đã
  thêm `require_owner_or_permission(user, "delete_review", review)` -> chỉ chủ sở hữu (hoặc admin có
  `delete_review`) mới sửa.
- **`GET /{id}` (detail):** trước không auth -> lộ review **chưa duyệt**. Đã gate: nếu
  `not is_approved` thì yêu cầu chủ sở hữu hoặc quyền `view_reviews` (khách ẩn danh -> 401). Review
  đã duyệt vẫn xem công khai. Sửa luôn error code khi không thấy: `E10200` -> `E10600`.

### 3. `file_controller.py` - PUT /{id} thiếu owner/quyền (đã vá 2026-07-01)

Phát hiện khi rà mở rộng toàn bộ controller (2026-07-01). `PUT /api/files/{id}` (sửa metadata file)
trước chỉ có `require_login()` -> bất kỳ user đăng nhập sửa/gán lại **file bất kỳ theo id** (đổi
`description/sort`, bật/tắt `isActive` để ẩn ảnh sản phẩm, gán lại `productId`/`reviewId`). IDOR +
thiếu phân quyền (upload gắn theo `user.id`, delete cần `delete_file`, riêng update để hở).

Đã vá: controller lấy file qua `get_file_by_id` rồi
`require_owner_or_permission(user, "delete_file", db_file, target_id=id)` - chủ file (theo
`file.user_id`) hoặc admin có `delete_file` mới sửa được. Không thêm quyền mới vào seed (dùng lại
`delete_file`). Test: `test/test_security.py::test_file_update_requires_owner_or_permission`.

## Quyết định: KHÔNG đổi (có chủ đích)

- **`file_download_controller.py` (`GET /media/{key}`) giữ CÔNG KHAI.** Đây là ảnh sản phẩm cho
  storefront (thẻ `<img>` của khách phải tải được, không gửi token). Key là đường dẫn ngẫu nhiên 32
  ký tự (`{2}/{2}/{rest}.ext`) nên khó đoán. Nếu sau này cần phục vụ tệp nhạy cảm (hóa đơn PDF...) thì
  phải tách endpoint có auth riêng - KHÔNG dùng `/media` công khai cho loại đó.
- **`category_controller`, `product_controller` GET, `review by_product`** công khai - hợp lý (nội
  dung storefront).

## Cơ chế phát hiện về sau

- Test nhất quán `test/test_permission_consistency.py`: chuỗi quyền dùng trong controller phải thuộc
  `PERMISSIONS` (seed). **KHÔNG** phát hiện được endpoint THIẾU kiểm tra -> phải rà thủ công.
- Test regression mới: [`test/test_security.py`](../../test/test_security.py) (5 test) khóa lại các
  bản vá trên (search cần quyền/đăng nhập; review create gán user đúng; update IDOR -> 403; detail
  review chưa duyệt -> 401).

## Nguyên tắc khi thêm endpoint mới (nhắc lại)

- Ghi dữ liệu / dữ liệu nhạy cảm -> `require_login()` + `_authz.require(<quyền>)` hoặc
  `require_owner_or_permission(...)`.
- Đọc dữ liệu của riêng người dùng (giỏ/wishlist/đơn/thông báo/địa chỉ) -> owner check
  (`require_owner_or_permission`) hoặc tối thiểu `require_login`.
- KHÔNG nhận `userId`/chủ sở hữu từ body cho tài nguyên gắn người dùng - luôn lấy từ user đăng nhập.
- Công khai chỉ cho nội dung storefront (sản phẩm, danh mục, review đã duyệt, ảnh media).
