# Tính năng nghiệp vụ

Mô tả các luồng nghiệp vụ chính. Bản đồ endpoint xem [API](api.md).

## Thanh toán (checkout)

Luồng đặt hàng đầy đủ gồm sổ địa chỉ, mã giảm giá, xem trước tổng tiền và phương thức thanh toán.

```text
Giỏ hàng ──► chọn địa chỉ ──► nhập coupon ──► POST /orders/preview (xem tổng tiền)
                                                  │
                                                  ▼
                                          POST /orders (tạo đơn)
                                     ┌────────────┴─────────────┐
                                  COD                       online (giả lập)
                                  đơn tạo xong          POST /orders/{id}/pay
                                                        ──► trang mock ──►
                                                        POST /payments/mock/callback
                                                        ──► đơn chuyển "đã thanh toán"
```

### Sổ địa chỉ

Mỗi người dùng có nhiều địa chỉ giao hàng (`user_addresses`), một địa chỉ có thể đặt làm mặc định.
Khi đặt hàng, địa chỉ được **chụp lại (snapshot)** vào đơn.

### Mã giảm giá (coupon)

Coupon nâng cấp so với bản gốc, cấu hình linh hoạt:

| Trường | Ý nghĩa |
|---|---|
| `discount_type` | `fixed` (số tiền) hoặc `percent` (%) |
| `max_discount` | Trần giảm khi `percent` (null = không trần) |
| `min_order_amount` | Đơn tối thiểu để áp mã (tính trên tiền hàng) |
| `applies_to` | `product` (giảm tiền hàng) hoặc `shipping` (giảm phí ship) |
| `usage_limit` / `used_count` | Tổng lượt cho phép / đã dùng |
| `per_user_once` | Mỗi người dùng chỉ dùng 1 lần |
| `start_date` / `end_date` / `is_active` | Hiệu lực |

### Xem trước và tạo đơn

- `POST /api/orders/preview` trả breakdown: `subtotal`, `shippingFee`, `productDiscount`,
  `shipDiscount`, `total`, `couponApplied`, `couponCode` - **không** tạo đơn.
- `POST /api/orders` tạo đơn từ `cartIds` + `addressId` + `couponCode?` + `paymentProvider`
  (`cod` | `mock_online`), nối đầy đủ phí ship và giảm giá vào `total_amount`. Toàn bộ nằm trong một
  transaction (trừ tồn kho + tạo `order_details` + áp coupon).

### Thanh toán online giả lập

Phục vụ demo, **không** phải cổng thật:

- `POST /api/orders/{id}/pay` (chỉ đơn `mock_online`, chưa thanh toán) trả `paymentRef` + `mockUrl`.
- Trang mock gọi `POST /api/payments/mock/callback` với `paymentRef` + `success` để chốt kết quả;
  thành công thì đơn chuyển `payment_status = true`.

## Thông báo in-app

Hộp thư theo người dùng (`notifications`). Hệ thống tự sinh thông báo khi: đặt hàng thành công, thanh
toán thành công, admin đổi trạng thái giao hàng.

- `GET /api/notifications/me` - hộp thư; `GET /me/unread-count` - badge chuông.
- `PATCH /api/notifications/{id}/read` (chỉ chủ sở hữu - chống IDOR); `PATCH /me/read-all`.
- `POST /api/notifications/broadcast` - admin gửi cho mọi user đang hoạt động.

## Email

Hai loại, quy tắc gửi khác nhau:

| Loại | Gửi | Ví dụ |
|---|---|---|
| Giao dịch | **nền** (fault-tolerant, lỗi chỉ log) | xác nhận đơn, thanh toán thành công, đổi trạng thái giao |
| Bảo mật | **đồng bộ** (người dùng đang chờ, báo lỗi rõ) | xác minh email, đặt lại mật khẩu, OTP |

- Cấu hình SMTP trong `application.yml` (khối `mail.smtp.*`). **Khi để trống username/password, email
  tự TẮT** - chỉ log, không gọi mạng, không chặn nghiệp vụ chính (tiện cho dev/test).
- Token email bảo mật lưu **dạng hash** trong `auth_tokens`, có TTL (xác minh 24h / reset 30 phút /
  OTP 5 phút). Đặt lại mật khẩu qua "quên mật khẩu" sẽ **thu hồi mọi refresh token** của user.

## Gợi ý / cá nhân hóa

Không dùng AI - chấm điểm theo luật trên hành vi người dùng.

```text
Hành động (view/add_to_cart/wishlist/purchase...) có trọng số
        │ ghi vào interactions
        ▼
user_category_affinity (materialized, decay theo thời gian)
        │
        ├──► for-you      : sản phẩm trong các danh mục ưa thích nhất
        ├──► recently-viewed: sản phẩm vừa xem
        └──► trending     : phổ biến toàn site (theo tín hiệu gần đây)

product_cooccurrence (cặp mua cùng) ──► related: "hay mua cùng"
```

- **Ghi tín hiệu tự động** khi user đăng nhập tương tác - client không cần gọi API log.
- **Affinity** danh mục được cập nhật ngay khi có tương tác (decay-on-write) và giảm dần theo thời gian.
- **Co-occurrence** (đồng mua) được XIME scheduler dựng lại định kỳ (hằng ngày 03:00); có endpoint
  admin để dựng lại thủ công.
- `for-you` khi chưa có dữ liệu (cold-start) tự trả về `trending`.

## Catalog và ảnh

- Sản phẩm có biến thể (SKU) qua thuộc tính/option; giá hiển thị = giá nhỏ nhất các option.
- DTO sản phẩm ở danh sách trả kèm `imageUrl` (ảnh đại diện), lấy theo batch để tránh N+1.
- Ảnh phục vụ qua `/media/{file_path}` (HTTP Range), nội dung nhị phân nằm trên đĩa.

## Dashboard

`GET /api/dashboard/stats` trả thống kê quản trị: doanh thu đã thanh toán, tổng đơn, đơn trong ngày,
đơn chưa thanh toán, tổng sản phẩm, option sắp hết hàng, tổng người dùng, tổng đánh giá, sản phẩm bán
chạy.
