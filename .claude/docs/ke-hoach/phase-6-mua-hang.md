# Phase 6 — Mua hàng (Cart, Order, Coupon)

**Mục tiêu:** Giỏ hàng, đơn hàng (gồm chi tiết), mã giảm giá — đặt hàng end-to-end.

> Nguồn PHP: `CartController/Service`, `OrderController/Service`, `OrderDetailController/Service`,
> `CouponController/Service`. Nghiệp vụ tồn kho/total_amount: [`../domain-model.md`](../domain-model.md).

## Bước

### Cart
- [x] **6.1** `cart_repository.py` — theo user, theo (user, product_option).
- [x] **6.2** `cart_service.py` — thêm/sửa/xóa item, xem giỏ. Áp quyền view/edit/delete_carts.
- [x] **6.3** DTO + `cart_controller.py`.

### Coupon
- [x] **6.4** `coupon_repository.py` — `find_by_code`, lọc còn hiệu lực.
- [x] **6.5** `coupon_service.py` — CRUD, kích hoạt/vô hiệu, kiểm tra hợp lệ (hạn, is_active).
- [x] **6.6** DTO + `coupon_controller.py`. Quyền: create/edit/delete/activate_deactivate_coupon.

### Order
- [x] **6.7** `order_repository.py`, `order_detail_repository.py`.
- [x] **6.8** `order_service.py` (order_detail tích hợp trong order_service):
  - Tạo đơn: **1 transaction** bọc cả order + order_details.
  - `total_amount` snapshot tại thời điểm đặt (không tính lại sau).
  - Trừ tồn kho (`product_options.stock`), xóa cart items.
  - Coupon chưa tích hợp (TODO).
- [x] **6.9** DTO request (tạo đơn từ giỏ) + response (đơn + chi tiết).
- [x] **6.10** `order_controller.py`. Quyền: view_orders, update_shipping_status, delete_order.

### Test thủ công
- [ ] **6.11** Thêm SP vào giỏ → đặt hàng → kiểm order + order_details + tồn kho giảm. Hủy đơn → tồn
  kho hồi. Đặt có coupon → giảm đúng.

## Đầu ra

Luồng mua hàng hoàn chỉnh, transaction đảm bảo toàn vẹn order + details + tồn kho.

## Rủi ro / cần xác minh

- ✅ Entity `Order` — **đã chốt (QĐ-2)**: dùng `product_discount`, `ship_discount`, `coupon_id` (nullable),
  `payment_status` kiểu **Boolean**. Áp coupon → set `coupon_id` + cập nhật 2 cột discount.
- Cách trừ/hồi tồn kho khi đặt/hủy — đọc kỹ `OrderService.php`. Cẩn thận race condition (khóa hàng?).
