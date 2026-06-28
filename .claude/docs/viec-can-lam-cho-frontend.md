# Việc backend cần làm để frontend hoàn thiện

> Tổng hợp ngày 2026-06-25 trong lúc dựng frontend Next.js (mô hình không proxy).
> Đây là các khoảng trống API mà frontend đang chờ. Mỗi mục ghi: vì sao cần + đề xuất endpoint/shape
> để frontend nối vào. Khi làm xong, cập nhật [`../docs/api-backend? (xem frontend)`] và báo lại frontend.

Liên quan: bản đồ API hiện có ở `D:\code\Monolithic\shop\frontend\.claude\docs\api-backend.md`,
kế hoạch frontend ở `...\frontend\.claude\docs\ke-hoach\`.

---

## 1. ✅ CORS + cookie cross-site - ĐÃ XONG

Đã bật CORSMiddleware + `application-production.yml` (samesite=none/secure khi `XIME_ENV=production`).
Xem [`luu-y-cau-hinh-cors.md`](luu-y-cau-hinh-cors.md). Không còn việc ở mục này, chỉ lưu ý khi deploy
prod: chạy HTTPS + sửa domain frontend cho khớp trong cả 2 file yaml.

---

## 2. ✅ `user_controller` - ĐĂNG KÝ + HỒ SƠ + USER CRUD - ĐÃ XONG

> Cập nhật 2026-06-25: đã thêm `app/controller/user_controller.py` (prefix `/api`). Đã chốt:
> đăng ký **chỉ trả message** (client tự gọi `/login` sau); admin có **CRUD đầy đủ**.
>
> Endpoint đã có:
> | Method | Path | Quyền | Body / Trả về |
> |---|---|---|---|
> | POST | `/api/register` | công khai | `{username, email, password, phone?, address?}` -> `{message}` (201) |
> | GET | `/api/me` | đăng nhập | -> `{id, username, email, phone, address, is_active}` |
> | PUT | `/api/me` | đăng nhập | `{email?, phone?, address?}` (cần >=1 trường) -> user đã cập nhật |
> | GET | `/api/me/permissions` | đăng nhập | -> `string[]` quyền hiệu lực (mục #6) |
> | GET | `/api/users?page=&limit=` | `view_users` | -> `UserResponse[]` (cả user đang khóa) |
> | GET | `/api/users/count` | `view_users` | -> `{total}` |
> | GET | `/api/users/{id}` | `view_user_details` | -> `UserResponse` |
> | POST | `/api/users` | `create_user` | `{username, email, password, phone?, address?, isActive?}` -> `UserResponse` (201) |
> | PUT | `/api/users/{id}` | `edit_user` hoặc chính chủ | mọi trường tùy chọn (cần >=1) -> `UserResponse` |
> | PATCH | `/api/users/{id}/active` | `activate_deactivate_user` | `{isActive}` -> `UserResponse` |
> | DELETE | `/api/users/{id}` | `delete_user` | -> `{message}` (chặn xóa `admin`/`superadmin` - E10101) |
>
> Lỗi trùng: username -> `E1006`, email -> `E1001`. Mật khẩu tối thiểu 6 ký tự (DTO).

**Hiện trạng (cũ):** không có controller nào cho user. Frontend không có: đăng ký, sửa hồ sơ/địa chỉ, lấy
user hiện tại, quản lý user (admin). Đang chặn các trang: `register`, `account/profile`,
`account/address`, và phần quản lý user trong store manager.

**Đã có (đừng làm lại):** `/api/change-password`, `/api/verify-password` (SecurityController);
`UserService` đã có `verify_user_password`, `change_user_password`, `get_user_by_id`...

**Cần bổ sung (đề xuất endpoint + shape để frontend nối thẳng):**

| Method | Path | Body | Trả về | Ghi chú |
|---|---|---|---|---|
| POST | `/api/register` | `{username, email, password, phone?, address?}` | `{accessToken}` hoặc `{message}` | Tạo user mới (hash bcrypt). Có thể auto-login (đặt luôn refresh cookie như `/login`) hoặc chỉ trả message rồi để client gọi `/login`. **Chốt giúp:** auto-login hay không. |
| GET | `/api/me` | (Bearer) | `{id, username, email, phone, address}` | Lấy user hiện tại. *Tùy chọn* - frontend đang giải mã JWT để lấy uid/username/email, nhưng KHÔNG có phone/address. Nếu muốn hiển thị/sửa phone+address thì cần endpoint này. |
| PUT | `/api/me` | `{email?, phone?, address?}` | user đã cập nhật | Sửa hồ sơ của chính mình. |
| GET | `/api/users?page=&limit=` | (quyền view_users) | `UserResponse[]` | Quản lý user (admin). |
| GET/POST/PUT/DELETE | `/api/users[/{id}]` | | | CRUD user (admin) nếu cần trang quản trị user. |

> Lưu ý validation: username/email unique → trả lỗi rõ (vd `E1xxx`) để frontend hiển thị "đã tồn tại".
> Mật khẩu nên có ràng buộc tối thiểu (độ dài) ở DTO request.

---

## 3. ✅ Phân trang - ĐÃ THÊM ENDPOINT COUNT

> Cập nhật 2026-06-25: đã chốt phương án (a) - thêm endpoint đếm riêng, KHÔNG đổi shape list
> (không breaking). Mỗi endpoint trả `{total}` (DTO `CountResponse`).
>
> Đã có: `GET /api/products/count` (công khai), `GET /api/orders/count` (`view_orders`),
> `GET /api/cart/count` (`view_carts`), `GET /api/files/count` (`view_files`),
> `GET /api/users/count` (`view_users`). Frontend gọi count + list để vẽ số trang.

### (Mô tả gốc)

**Hiện trạng:** các endpoint list (`/api/products`, `/api/orders/all`, `/api/group`, `/api/files`,
`/api/cart/all`...) nhận `page`+`limit` nhưng trả **list thuần**, không có `total`/`totalPages`.

**Hệ quả:** frontend không vẽ được số trang chính xác; chỉ suy "còn trang sau" khi `len == limit`.

**Đề xuất (chọn 1):**
- (a) Thêm endpoint đếm riêng, vd `GET /api/products/count` → `{total}`; hoặc
- (b) Đổi response list sang `{items: [...], total, page, limit}` (nhất quán cho mọi list). **Khuyến
  nghị (b)** nhưng là breaking change - nếu làm, báo frontend để sửa đồng loạt.

> Nếu giữ nguyên (không làm), frontend dùng phương án suy "hết trang" - chấp nhận được cho MVP.

---

## 4. Coupon chưa vào luồng đặt hàng

**Hiện trạng:** `OrderCreateRequest` chỉ nhận `{cartIds, address, paymentMethod}`. Entity `orders` có
`coupon_id` nullable + `product_discount`/`ship_discount`, nhưng API tạo đơn không nhận mã giảm giá và
không tính lại tổng theo coupon.

**Cần (nếu muốn có tính năng áp mã lúc thanh toán):**
- Cho phép `OrderCreateRequest` nhận thêm `couponCode?` (hoặc `couponId?`).
- Service kiểm tra coupon hợp lệ (còn hạn, is_active), tính `product_discount`/`ship_discount`, gắn
  `coupon_id`, và chốt `total_amount` đã trừ giảm giá.
- *Tùy chọn:* endpoint `POST /api/coupons/apply` `{code, subtotal}` → `{discount, valid}` để frontend
  xem trước mức giảm trước khi đặt.

---

## 5. Trang chủ: best-sell / special / suggest (đang CHỜ backend)

**Hiện trạng:** bản frontend cũ có 3 mục này; backend mới chỉ có `products.popularity` và
`interactions`/`actions` (migrate schema, chưa có logic). Không có endpoint trả "sản phẩm bán chạy /
nổi bật / gợi ý".

**Đề xuất endpoint (frontend sẽ nối khi có):**
| Path | Ý nghĩa | Gợi ý nguồn |
|---|---|---|
| `GET /api/products/best-sell?limit=` | Bán chạy | theo tổng số đã bán (order_details) hoặc `popularity` |
| `GET /api/products/special?limit=` | Nổi bật/khuyến mãi | theo `discount_percentage > 0` hoặc cờ riêng |
| `GET /api/products/suggest?limit=` | Gợi ý | theo `popularity` hoặc `interactions` của user |

> Trước mắt frontend để TRỐNG các mục này. Khi backend có, chỉ cần khai báo thêm hàm gọi + section.
> Lưu ý: dashboard service đã tính `topProducts` (bán chạy) - có thể tái dùng logic đó cho best-sell.

---

## 6. ✅ Quyền hiệu lực của user - ĐÃ THÊM `GET /api/me/permissions`

> Cập nhật 2026-06-25: thêm `GET /api/me/permissions` (cần đăng nhập) -> trả `string[]` tên các
> quyền user hiện tại thực sự có (ví dụ `["create_product", "view_orders", ...]`). Frontend dùng để
> ẩn/hiện menu store manager thay vì dựa vào 403. JWT vẫn KHÔNG nhồi quyền (giữ token gọn).

### (Mô tả gốc)

## 6b. Quyền của user không nằm trong JWT (gate UI admin)

**Hiện trạng:** access token chứa `uid, username, email, isActive` nhưng KHÔNG có danh sách quyền.
Phân quyền thực thi phía server (`AuthorizationService.require`). Frontend không biết user có quyền gì
để ẩn/hiện menu admin.

**Hiện frontend xử lý tạm:** thử gọi endpoint, gặp `403 (E2021)` thì ẩn. Hoạt động nhưng không mượt.

**Đề xuất (tùy chọn, cải thiện UX admin):**
- `GET /api/me/permissions` → `["create_product", "view_orders", ...]` (quyền hiệu lực của user hiện
  tại), hoặc nhồi thêm claim `permissions` vào access token khi đăng nhập.
- Khi có, frontend sẽ ẩn/hiện menu store manager theo quyền thay vì dựa vào 403.

---

## 7. ✅ Reviews theo sản phẩm - ĐÃ XONG

> Cập nhật 2026-06-25: thêm `GET /api/reviews/product/{productId}?page=&limit=` (công khai, KHÔNG cần
> đăng nhập). Chỉ trả review `is_approved=true` của sản phẩm, mới nhất trước, có phân trang. Frontend
> nối thẳng vào phần "đánh giá" trên trang chi tiết. Form gửi đánh giá vẫn là `POST /api/reviews`
> (cần đăng nhập).

---

## 8. (Tùy chọn) Nhúng ảnh đại diện vào DTO danh sách sản phẩm

**Hiện trạng:** product DTO (`product_service._to_dto`) không kèm ảnh. Ảnh phải lấy riêng qua
`GET /api/files/product/{id}` → N+1 khi render lưới sản phẩm (home/danh mục/tìm kiếm).

**Đề xuất:** thêm field `thumbnail` (hoặc `images: [file_path...]`) vào product DTO list/detail để
frontend render ảnh trong 1 request. Trước mắt frontend KHÔNG hiển thị ảnh ở lưới (chỉ tên + giá), chỉ
hiển thị ảnh ở trang chi tiết. Có ảnh trong DTO sẽ bật được ảnh ở lưới + cải thiện SEO.

---

## 9. ✅ Cart item kèm tên + đơn giá - ĐÃ XONG

> Cập nhật 2026-06-25: `CartController._item_to_dict` giờ trả thêm `productId`, `productName`,
> `price` (đơn giá option), `subtotal` (= price * quantity). Gộp 1 transaction
> (`ProductService.get_cart_item_detail`) tránh N+1. Frontend hiển thị tên/giá/thành tiền từng dòng
> và tính tạm tính client. (Tổng cuối vẫn do backend chốt khi tạo đơn.) `thumbnail` chưa có - phụ
> thuộc mục #8 (chưa làm).

---

## 10. ✅ Wishlist list kèm id để xóa - ĐÃ XONG (theo phương án a)

> Cập nhật 2026-06-25: `GET /api/wishlist` giờ trả `[{wishlistId, productId, name}]`. Frontend gọi
> `DELETE /api/wishlist/{wishlistId}` với `wishlistId` lấy từ list. Đã làm theo (a).
>
> Đính chính tài liệu cũ: entity `wishlist` thực tế lưu theo **product** (`product_id`), và
> `POST /api/wishlist` nhận `{productId}` (không phải `productOptionId`). Nên KHÔNG có lệch
> product/option - wishlist nhất quán theo product như bản cũ.

---

## Trạng thái (cập nhật 2026-06-25)

**Đã xong:** #1 CORS, #2 user_controller (đăng ký + hồ sơ + admin CRUD), #3 endpoint count,
#6 `/api/me/permissions`, #7 review theo sản phẩm, #9 cart kèm tên/giá, #10 wishlist kèm id.

**Còn lại (chưa làm - chờ quyết định khi cần):**
- **#4 coupon trong đơn** - cần chốt: `discount` là % hay số tiền, áp vào product hay ship.
- **#5 trang chủ best-sell/special/suggest** - best-sell/special làm nhanh được (tái dùng
  `top_selling` + `discount_percentage`); suggest chưa rõ logic.
- **#8 thumbnail trong product DTO** - đánh đổi coupling product_service <-> file_service; cũng mở
  được `thumbnail` cho cart item (#9) khi làm.
