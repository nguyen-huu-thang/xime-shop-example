# Domain Model — Schema, Quan hệ & Nghiệp vụ

> Nguồn: `D:\code\PHP\shop-backend\giải thích cơ sở dữ liệu.txt` + các file `src/Entity/*.php`.
> Đọc file gốc để nắm trọn vẹn giải thích nghiệp vụ (bằng tiếng Việt, rất chi tiết).

## 25 Entity cần migrate

### Người dùng & phân quyền
| Bảng | Khóa chính | Cột chính | Ghi chú nghiệp vụ |
|---|---|---|---|
| `users` | id (bigint, auto) | username(unique), email(unique), password(hash), phone, address, is_active, created_at, updated_at | Tài khoản người dùng |
| `permissions` | id | name(unique), description, **default_allow** (Boolean, default False) | Danh mục quyền hệ thống (~55 quyền). Cột `default_allow` (QĐ-3) là fallback của `check_permission`. Xem [`phan-quyen.md`](phan-quyen.md) |
| `groups` | id | name(unique), description | Nhóm người dùng (vd: admin) |
| `group_members` | id | user_id→users, group_id→groups, unique(user_id,group_id) | Liên kết user ↔ group |
| `user_permissions` | id | user_id, permission_id, target_id, is_active, is_denied | Quyền cấp trực tiếp cho user |
| `group_permissions` | id | group_id, permission_id, target_id, is_active, is_denied | Quyền cấp cho nhóm |

### Danh mục & sản phẩm
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| `categories` | name(unique), description, parent_id→categories | **Cây phân cấp cha-con** (vd: thời trang/dép/dép lê) |
| `products` | name, description, location_address, category_id, popularity, is_active, is_delete | `location_address`=cơ sở bán; `popularity`=điểm gợi ý |
| `product_attributes` | product_id, name | Loại lựa chọn: size, màu... |
| `product_attribute_values` | attribute_id, value | Giá trị: 40, 41, đỏ... |
| `product_options` | product_id, price, stock | **Một tổ hợp lựa chọn hoàn chỉnh** = 1 SKU có giá + tồn kho |
| `product_option_values` | option_id, attribute_value_id | Bảng nối nhiều-nhiều option ↔ attribute_value |

> **Cơ chế tùy chọn sản phẩm (quan trọng):** một sản phẩm có nhiều `product_attributes` (hàng lựa chọn),
> mỗi attribute có nhiều `product_attribute_values` (cột). Người dùng chọn đủ mỗi hàng 1 giá trị →
> xác định duy nhất 1 `product_options` (có giá + tồn kho). Sản phẩm không có lựa chọn → vẫn tạo 1
> `product_options` duy nhất, `product_attributes` rỗng.

### Mua hàng
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| `cart` | user_id, product_option_id, quantity, created_at | Giỏ hàng (theo option, không theo product) |
| `wishlist` | user_id, product_option_id, created_at | Danh sách yêu thích |
| `user_addresses` | user_id, recipient_name, recipient_phone, province, district, ward, detail, lat, lng, is_default, created_at, updated_at | **Sổ địa chỉ giao hàng** (checkout). Tọa độ lat/lng (nullable) để hiển thị bản đồ; tối đa 1 is_default/user. Cascade khi xóa user. Xem [`thiet-ke-checkout.md`](thiet-ke-checkout.md) |
| `coupons` | code(unique), discount, start_date, end_date, is_active, **discount_type**(fixed/percent), **max_discount**(nullable), **min_order_amount**, **applies_to**(product/shipping), **usage_limit**(nullable), **used_count**, **per_user_once** | Mã giảm giá - đã nâng cấp (loại %/số tiền + trần, đơn tối thiểu, scope SP/ship, giới hạn lượt dùng) |
| `orders` | user_id, total_amount, payment_method, address, shipping_status, payment_status (**bool**), shipping_fee, product_discount, ship_discount, coupon_id (nullable), **recipient_name/recipient_phone/ship_lat/ship_lng** (snapshot địa chỉ giao), **payment_provider**(cod/mock_online), **payment_ref**(nullable), **paid_at**(nullable), created_at, updated_at | `total_amount` chốt tại thời điểm đặt = subtotal + shipping_fee - product_discount - ship_discount. Snapshot địa chỉ + tọa độ giao lúc đặt. |
| `order_details` | order_id, product_option_id, quantity, price | Chi tiết từng dòng hàng trong đơn |

> **Tồn kho:** số tồn hiện tại = stock − số đã đặt; hủy đơn thì cộng lại. Không có hệ thống kho riêng.
> **Entity `Order` — đã chốt (QĐ-2):** lấy `Order.php` làm chuẩn (`product_discount`, `ship_discount`,
> `address`, `payment_status` kiểu Boolean) + thêm `coupon_id` nullable. Chi tiết:
> [`quyet-dinh-thiet-ke.md`](quyet-dinh-thiet-ke.md#qđ-2-entity-order--lấy-code-orderphp-làm-chuẩn-thêm-coupon_id).

### Tương tác & nội dung
| Bảng | Cột chính | Ghi chú |
|---|---|---|
| `reviews` | product_id, user_id, rating, comment, is_approved, created_at | Đánh giá, cần duyệt |
| `notifications` | user_id, title, message, type(email/sms/push), **link**(nullable), is_read, read_at, created_at | Hộp thư thông báo theo user; `link` để FE bấm điều hướng (vd /orders/12). Xem [`thiet-ke-thong-bao.md`](thiet-ke-thong-bao.md) |
| `interactions` | user_id, product_id, action_id, created_at | Lịch sử tương tác (gợi ý SP) |
| `actions` | name(unique), description, score | Loại hành động + điểm |

> `interactions`/`actions` PHP gốc "để làm màu, không code logic". Migrate **schema** nhưng có thể bỏ logic.

### Hạ tầng
| Bảng | Khóa chính | Cột chính | Ghi chú |
|---|---|---|---|
| `files` | id | user_id, file_name, file_path, file_size, sort, uploaded_at, is_active, list_tables→list_tables, description | Quan hệ đa hình qua `list_tables` |
| `list_tables` | table_name (pk) | description | Liệt kê tên bảng — phục vụ quan hệ đa hình của `files` |
| `refresh_tokens` | id (varchar 64) | expires_at, **user_id** (nullable, FK users) | Lưu id token + hạn + chủ sở hữu; `user_id` để thu hồi mọi phiên khi reset mật khẩu |
| `blacklist_tokens` | id (varchar 64) | expires_at | id access token đã logout (thu hồi) |
| `auth_tokens` | id (bigint) | user_id (FK users), type(verify_email/reset_password/otp), token_hash(SHA-256), expires_at, used_at, attempts, created_at | Token/mã dùng một lần cho email bảo mật (1 bảng chung). Xem [`thiet-ke-email.md`](thiet-ke-email.md) |

> **File storage:** tên file = 32 ký tự ngẫu nhiên, lưu tại
> `/public/data/{2 ký tự đầu}/{2 ký tự tiếp}/{phần còn lại}`. Đổi tên để giảm rủi ro bảo mật
> (tránh đoán đường dẫn file thực thi). Quan hệ file↔entity là 1-nhiều, khóa ngoại "đa hình" đặt ở
> `files` qua cặp (`list_tables` = tên bảng, `id` bản ghi).

## Quan hệ tổng quát (ERD rút gọn)

```
users 1─* group_members *─1 groups
users 1─* user_permissions *─1 permissions
groups 1─* group_permissions *─1 permissions
categories 1─* categories (self, parent_id)
categories 1─* products
products 1─* product_attributes 1─* product_attribute_values
products 1─* product_options *─* product_attribute_values (qua product_option_values)
users 1─* cart *─1 product_options
users 1─* wishlist *─1 product_options
users 1─* orders 1─* order_details *─1 product_options
coupons 1─* orders
products 1─* reviews *─1 users
users 1─* notifications
users 1─* interactions *─1 products, *─1 actions
list_tables 1─* files *─1 users
```

## Lưu ý khi tạo SQLAlchemy entity

- ID dùng `BigInteger` cho hầu hết bảng (PHP dùng `bigint`); `refresh_tokens`/`blacklist_tokens` dùng `String(64)`; `list_tables` PK là `table_name` (String).
- Cột timestamp mặc định `CURRENT_TIMESTAMP` → dùng `server_default=func.now()`.
- Tạo mixin `TimestampMixin` (created_at/updated_at) tái dùng.
- Boolean default: `is_active=True`, `is_denied=False`, `is_approved=False`, `is_read=False`.
- Đối chiếu **cả** `src/Entity/*.php` **và** file `giải thích cơ sở dữ liệu.txt`. Các khác biệt đã chốt
  (Order, permissions.default) → theo [`quyet-dinh-thiet-ke.md`](quyet-dinh-thiet-ke.md).
- `permissions.default_allow`: KHÔNG đặt tên cột là `default` (từ khóa SQL). Dùng `default_allow`.
