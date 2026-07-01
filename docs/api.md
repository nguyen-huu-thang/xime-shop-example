# API

REST API qua FastAPI (XIME WebAdapter). Tài liệu tương tác (Swagger) tại `http://localhost:8088/docs`.

## Quy ước chung

- **Thành công**: trả thẳng dữ liệu (object hoặc mảng), không bọc `{data: ...}`.
- **Lỗi nghiệp vụ**: HTTP 4xx/5xx + body `{ "errorKey", "code", "message", "details"? }`. Xem
  [Lỗi và mã lỗi](loi-va-ma-loi.md).
- **Phân trang**: tham số `?page=&limit=`; tổng số lấy qua endpoint `.../count` riêng.
- **Xác thực**: gửi `Authorization: Bearer <accessToken>`. Refresh token nằm trong httpOnly cookie.
- **Casing**: phần lớn response camelCase; một số nhóm (category, review, coupon, notification, file,
  user) là snake_case. Khi nghi ngờ, đối chiếu `app/dto/response/`.

Cột "Quyền" bên dưới: `công khai` = không cần đăng nhập; `đăng nhập` = chỉ cần token; tên quyền cụ thể
= cần quyền đó (hoặc là chủ sở hữu, với endpoint chi tiết).

## Xác thực và tài khoản

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/login` | công khai | Đăng nhập, trả `accessToken` + đặt cookie refresh |
| POST | `/api/refresh-token` | cookie | Cấp access mới + xoay refresh token |
| GET | `/api/logout` | đăng nhập | Đăng xuất (thu hồi token) |
| POST | `/api/change-password` | đăng nhập | Đổi mật khẩu |
| POST | `/api/verify-password` | đăng nhập | Xác minh lại mật khẩu hiện tại |
| POST | `/api/register` | công khai | Tự đăng ký tài khoản |
| GET | `/api/me` | đăng nhập | Thông tin người dùng hiện tại |
| GET | `/api/me/permissions` | đăng nhập | Danh sách quyền hiệu lực |
| PUT | `/api/me` | đăng nhập | Tự cập nhật hồ sơ |

### Email bảo mật

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/verify-email` | công khai | Xác minh email bằng token |
| POST | `/api/verify-email/resend` | đăng nhập | Gửi lại email xác minh |
| POST | `/api/forgot-password` | công khai | Gửi liên kết đặt lại (luôn trả 200) |
| POST | `/api/reset-password` | công khai | Đặt lại mật khẩu bằng token |
| POST | `/api/otp/request` | đăng nhập | Gửi OTP qua email |
| POST | `/api/otp/verify` | đăng nhập | Xác thực OTP |

## Người dùng và phân quyền (quản trị)

| Method | Path | Quyền |
|---|---|---|
| GET | `/api/users` (+`/count`, `/{id}`) | `view_users` |
| POST | `/api/users` | `create_user` |
| PUT/PATCH/DELETE | `/api/users/{id}` (+`/active`) | quyền tương ứng |
| GET | `/api/permission` | `view_permissions` |
| GET/POST/PUT/DELETE | `/api/group`, `/api/group-member`, `/api/group-permissions`, `/api/user-permissions` | quyền nhóm/quyền tương ứng |

## Catalog

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/categories` (+`/{id}`, `/{id}/subcategories`) | công khai | Danh mục |
| POST/PUT/DELETE | `/api/categories` (+`/{id}`) | quyền danh mục | Quản trị danh mục |
| GET | `/api/products` (+`/count`) | công khai | Danh sách sản phẩm (kèm `imageUrl`) |
| GET | `/api/products/{id}` | công khai | Chi tiết (ghi tín hiệu "view" nếu đăng nhập) |
| GET | `/api/products/by-category/{categoryId}` | công khai | Theo danh mục |
| GET | `/api/products/{id}/option-default` | công khai | Option mặc định (giá/tồn) |
| POST | `/api/products/{id}/find-option` | công khai | Tìm option khớp tổ hợp thuộc tính |
| GET | `/api/products/{id}/related` | công khai | Sản phẩm hay mua cùng |
| GET | `/api/products/managed` (+`/count`) | đăng nhập | Sản phẩm theo mảng danh mục nhân viên phụ trách |
| POST/PUT/DELETE | `/api/products` (+`/{id}`, `/{id}/attribute`) | quyền sản phẩm | Quản trị sản phẩm/biến thể |

## Tệp / ảnh

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/files/product/{product_id}` | công khai | Ảnh của sản phẩm |
| GET | `/media/{key}` | công khai | Stream nội dung tệp (hỗ trợ HTTP Range) |
| GET | `/api/files` (+`/all`, `/count`, `/inactive`, `/{id}`, `/user/{id}`) | `view_files` | Quản trị tệp |
| POST/PUT/DELETE | `/api/files` (+`/{id}`) | quyền tệp | Upload/sửa/xóa |

## Giỏ - Yêu thích - Đánh giá

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/cart` | đăng nhập | Giỏ của tôi |
| POST | `/api/cart` | đăng nhập | Thêm vào giỏ của mình (self-service) |
| PUT/DELETE | `/api/cart/{id}` | chủ sở hữu | Sửa/xóa dòng giỏ |
| GET | `/api/cart/all` (+`/count`, `/{id}`) | `view_carts` | Quản trị giỏ |
| GET | `/api/wishlist` | đăng nhập | Yêu thích của tôi |
| POST/DELETE | `/api/wishlist` (+`/{id}`) | đăng nhập / chủ | Thêm/xóa |
| GET | `/api/wishlist/all` | `view_wishlists` | Quản trị |
| GET | `/api/reviews/product/{product_id}` | công khai | Đánh giá đã duyệt của sản phẩm |
| POST | `/api/reviews` | đăng nhập | Gửi đánh giá (chờ duyệt, gán theo user đăng nhập) |
| PUT | `/api/reviews/{id}` | chủ sở hữu | Sửa đánh giá của mình |
| GET | `/api/reviews` (+`/{id}`) | `view_reviews` / chủ | Quản trị / chi tiết |
| PATCH | `/api/reviews/{id}/approve` (+`/disapprove`) | `approve_disapprove_review` | Duyệt |
| DELETE | `/api/reviews/{id}` | `delete_review` | Xóa |

## Thanh toán

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| GET/POST/PUT/DELETE | `/api/addresses` (+`/{id}`, `/{id}/default`) | đăng nhập | Sổ địa chỉ của tôi |
| POST | `/api/orders/preview` | đăng nhập | Xem trước tổng tiền (subtotal/ship/giảm/total) |
| POST | `/api/orders` | đăng nhập | Tạo đơn theo `cartIds` + `addressId` + `couponCode?` + `paymentProvider` |
| GET | `/api/orders` | đăng nhập | Đơn của tôi |
| GET | `/api/orders/{id}` | chủ / `view_order_details` | Chi tiết đơn |
| POST | `/api/orders/{id}/pay` | chủ | Khởi tạo thanh toán online giả lập |
| POST | `/api/payments/mock/callback` | công khai | Callback từ cổng thanh toán giả lập |
| GET | `/api/orders/all` (+`/count`) | `view_orders` | Quản trị đơn |
| PUT | `/api/orders/{id}/shipping-status` | đăng nhập (quyền) | Đổi trạng thái giao (thông báo cho chủ đơn) |
| DELETE | `/api/orders/{id}` | `delete_order` | Xóa đơn |
| GET/POST/PUT/DELETE | `/api/coupons` (+`/{id}`) | quyền coupon | Quản trị mã giảm giá |

## Thông báo

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/notifications/me` (+`/me/unread-count`) | đăng nhập | Hộp thư của tôi + đếm chưa đọc |
| PATCH | `/api/notifications/{id}/read` (+`/me/read-all`) | chủ sở hữu | Đánh dấu đã đọc |
| GET/POST | `/api/notifications` (+`/{id}`) | `view_notifications` / `create_notification` | Quản trị |
| POST | `/api/notifications/broadcast` | `create_notification` | Gửi tới mọi user đang hoạt động |

## Gợi ý / cá nhân hóa

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/recommendations/trending` | công khai | Thịnh hành |
| GET | `/api/recommendations/recently-viewed` | đăng nhập | Đã xem gần đây |
| GET | `/api/recommendations/for-you` | đăng nhập | Gợi ý cho bạn (cold-start -> trending) |
| POST | `/api/recommendations/admin/rebuild-cooccurrence` | `manage_recommendations` | Dựng lại "mua cùng" thủ công |

> Backend **tự ghi tín hiệu** khi user đăng nhập tương tác (xem/giỏ/wishlist/mua) - client không gọi
> API ghi log.

## Khác

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/search/products` (+`/products/category`) | công khai | Tìm sản phẩm |
| GET | `/api/search/users`, `/groups` | quyền admin | Tìm (quản trị) |
| GET | `/api/search/cart`, `/orders` | đăng nhập | Tìm trong dữ liệu của mình |
| GET | `/api/dashboard/stats` | `access_admin_dashboard` | Thống kê quản trị |
| GET/POST | `/api/email/status`, `/test` | quyền admin | Kiểm tra cấu hình SMTP |
| GET | `/api/health` | công khai | Health check |
