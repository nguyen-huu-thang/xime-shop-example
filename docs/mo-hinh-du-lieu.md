# Mô hình dữ liệu

CSDL là **PostgreSQL**, định nghĩa bằng SQLAlchemy entity (`app/entity/`) và migrate bằng Alembic.
Tài liệu này mô tả các bảng chính theo nhóm nghiệp vụ. Tên cột dùng `snake_case`.

## Catalog: sản phẩm và biến thể

Mô hình biến thể (SKU) tách thuộc tính - giá trị - option:

```text
categories (cây, parent_id tự tham chiếu)
    │ 1-n
products ──1-n── product_attributes ──1-n── product_attribute_values
    │                                              │
    │ 1-n                                          │ (n-n qua product_option_values)
product_options ──1-n── product_option_values ────┘
```

| Bảng | Ý nghĩa | Cột chính |
|---|---|---|
| `categories` | Danh mục, dạng cây | `id`, `name`, `parent_id` |
| `products` | Sản phẩm | `id`, `name`, `description`, `category_id`, `discount_percentage`, `is_active`, `is_delete` |
| `product_attributes` | Thuộc tính của 1 sản phẩm (vd "Màu") | `id`, `product_id`, `name` |
| `product_attribute_values` | Giá trị thuộc tính (vd "Đỏ") | `id`, `attribute_id`, `value` |
| `product_options` | Một option (SKU) = tổ hợp lựa chọn | `id`, `product_id`, `price`, `stock` |
| `product_option_values` | Nối option với các giá trị thuộc tính | `id`, `option_id`, `attribute_value_id` |

- Sản phẩm không biến thể: dùng một option mặc định (không gắn giá trị thuộc tính).
- Giá hiển thị của sản phẩm = giá nhỏ nhất trong các option; tồn kho = tổng option.

## Tệp / ảnh (quan hệ đa hình)

| Bảng | Ý nghĩa | Cột chính |
|---|---|---|
| `files` | Tệp gắn với một bản ghi bất kỳ | `id`, `file_path`, `target_id`, `list_table_id`, `sort`, `is_active`, `user_id` |
| `list_table` | Danh sách tên bảng cho quan hệ đa hình (vd `products`, `reviews`) | `id` (text) |

Ảnh sản phẩm là `files` có `list_table_id = 'products'` và `target_id = product.id`. Nội dung nhị phân
nằm trên đĩa (`storage.local.root`), DB chỉ lưu `file_path`; phục vụ qua `/media/{file_path}` (hỗ trợ
HTTP Range). DTO sản phẩm trả kèm `imageUrl` (ảnh đại diện = file đầu theo `sort`).

## Người dùng và địa chỉ

| Bảng | Ý nghĩa | Cột chính |
|---|---|---|
| `users` | Tài khoản | `id`, `username`, `email`, `password` (hash), `is_active`, `email_verified`, `is_superadmin` |
| `user_addresses` | Sổ địa chỉ giao hàng | `id`, `user_id`, `recipient_name`, `recipient_phone`, `province`, `district`, `ward`, `detail`, `lat`, `lng`, `is_default` |

## Mua hàng và thanh toán

```text
users ──1-n── cart ──n-1── product_options
users ──1-n── wishlist ──n-1── products
users ──1-n── orders ──1-n── order_details ──n-1── products
orders ──n-1── coupons (tùy chọn)
```

| Bảng | Ý nghĩa | Cột chính |
|---|---|---|
| `cart` | Giỏ hàng theo người dùng | `id`, `user_id`, `product_option_id`, `quantity` |
| `wishlist` | Yêu thích theo sản phẩm | `id`, `user_id`, `product_id` |
| `orders` | Đơn hàng | `id`, `user_id`, `total_amount`, `payment_method`, `payment_status`, `shipping_status`, `shipping_fee`, `product_discount`, `ship_discount`, `coupon_id`, `address` |
| `order_details` | Dòng đơn (snapshot tên/giá lúc đặt) | `id`, `order_id`, `product_id`, `name`, `quantity`, `price`, `attribute` |
| `coupons` | Mã giảm giá | `id`, `code`, `discount`, `discount_type` (`fixed`/`percent`), `max_discount`, `min_order_amount`, `applies_to` (`product`/`shipping`), `usage_limit`, `used_count`, `per_user_once`, `start_date`, `end_date`, `is_active` |
| `reviews` | Đánh giá sản phẩm | `id`, `product_id`, `user_id`, `rating`, `comment`, `is_approved` |

## Phân quyền

```text
users ──n-n── groups        (qua group_members)
groups ──1-n── group_permissions ──n-1── permissions
users  ──1-n── user_permissions  ──n-1── permissions
```

| Bảng | Ý nghĩa | Cột chính |
|---|---|---|
| `permissions` | Danh mục quyền | `id`, `name`, `description`, `default_value`, `scope_type` |
| `groups` | Nhóm quyền | `id`, `name` |
| `group_members` | Thành viên nhóm | `user_id`, `group_id` |
| `group_permissions` | Cấp quyền cho nhóm | `group_id`, `permission_id`, `target_id`, `is_active`, `is_denied` |
| `user_permissions` | Cấp quyền cho cá nhân | `user_id`, `permission_id`, `target_id`, `is_active`, `is_denied` |

Chi tiết cách đánh giá (deny-overrides, scope theo nhánh danh mục): [Phân quyền](phan-quyen.md).

## Thông báo và token

| Bảng | Ý nghĩa | Cột chính |
|---|---|---|
| `notifications` | Thông báo in-app theo người dùng | `id`, `user_id`, `title`, `message`, `type`, `link`, `is_read`, `read_at` |
| `auth_tokens` | Token email bảo mật (lưu hash) | `id`, `user_id`, `type` (`verify_email`/`reset_password`/`otp`), `token_hash`, `expires_at` |
| `refresh_tokens` | Refresh token (theo người dùng, để thu hồi) | `id`, `user_id`, `expires_at` |
| `blacklist_tokens` | Access token bị thu hồi | `id`, `expires_at` |

## Cá nhân hóa

| Bảng | Ý nghĩa | Cột chính |
|---|---|---|
| `actions` | Loại hành động + trọng số | `id`, `name`, `score` |
| `interactions` | Sự kiện người dùng - sản phẩm | `id`, `user_id`, `product_id`, `action_id`, `created_at` |
| `user_category_affinity` | Độ ưa thích danh mục (materialized, decay-on-write) | `user_id`, `category_id`, `score`, `updated_at` |
| `product_cooccurrence` | Cặp sản phẩm hay mua cùng | `product_id`, `co_product_id`, `score` |

Cách chấm điểm và dùng để gợi ý: [Tính năng](tinh-nang.md#gợi-ý--cá-nhân-hóa).
