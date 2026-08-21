# Rà soát backend + vá lỗi nghiêm trọng/trung bình (2026-07-01)

> Rà soát toàn bộ backend (order/cart/coupon/pricing/payment, auth/JWT/authorization,
> product/file/notification/user, handler, DTO, repository) tìm lỗi tiềm ẩn về logic,
> concurrency, validate. Đã vá các mục nghiêm trọng (#1, #2) và trung bình (#3-#6).
> Test: 160 passed (153 cũ + 7 regression mới trong `test/test_hardening.py`).

## Đã vá

### #1 (nghiêm trọng) Bán vượt tồn kho + lạm dụng coupon do race condition
Trước: `order_service.create_order` đọc `opt.stock` rồi `opt.stock -= qty` KHÔNG khóa dòng ->
hai đơn đồng thời cùng trừ -> tồn kho âm. Coupon `usage_limit`/`per_user_once` cũng TOCTOU.

Vá:
- `ProductOptionRepository.find_for_update(id)` và `CouponRepository.find_for_update(id)` +
  `find_by_code(code, for_update=True)` dùng `SELECT ... FOR UPDATE`.
- `create_order` (COD) khóa dòng option trước khi trừ kho; `coupon_svc.resolve(..., for_update=True)`
  khóa coupon trước khi tăng `used_count`.
- `confirm_mock_payment` (online) khóa option + coupon khi trừ kho/tăng lượt lúc thanh toán.

### #2 (nghiêm trọng) Phân trang không kẹp -> 500 (và rủi ro DoS)
Trước: controller nhận `page/limit` tùy ý; `offset=(page-1)*limit` ÂM khi `page<=0` ->
PostgreSQL lỗi `OFFSET must not be negative` -> 500; `limit` không trần.

Vá: helper `app/pagination.py::paginate(page, limit)` kẹp `page>=1`, `1<=limit<=100`, trả
`(offset, limit)` an toàn. Áp vào 8 repository phân trang + `search_service`.

### #3 (trung bình) Tồn kho: GIỮ CHỖ kiểu Shopee (cập nhật 2026-07-01, thay hướng cũ)
Quyết định người dùng (bản chốt): **đặt hàng thành công là trừ kho NGAY** (kể cả online) để
tránh cảnh khách săn mã/hàng hiếm mà kho chỉ trừ lúc thanh toán. Đơn online có **hạn thanh toán
1 ngày**; quá hạn chưa trả thì **hoàn kho + hủy đơn**.
- COD và online: đều khóa dòng option + trừ kho + tăng lượt coupon NGAY lúc đặt.
- Online (`mock_online`): thêm `order.payment_deadline = now + 1 ngày` (hằng
  `OrderService._online_payment_ttl`). `confirm_mock_payment` giờ chỉ đánh dấu đã thanh toán
  (kho đã trừ), và TỪ CHỐI nếu đơn đã hủy (`cancelled_at`) -> E10509. `start_payment` cũng chặn
  đơn đã hủy.
- Hết hạn: `OrderService.expire_overdue_online_orders(cutoff=None)` cộng lại tồn kho từng dòng
  (khóa option), nhả lượt coupon (`decrement_usage`), set `cancelled_at` + trạng thái hủy. Chạy
  bởi `ExpireOrdersJob` (scheduler mỗi 10 phút). `count_by_coupon_and_user` loại đơn đã hủy để
  `per_user_once` được dùng lại mã sau khi đơn hủy.
- Cột mới: `order_details.product_option_id` (migration `f7b8c9d0e1a2`) để trừ/hoàn đúng option;
  `orders.payment_deadline` + `orders.cancelled_at` (migration `a8c9d0e1f2b3`).

### #4 (trung bình) `update_cart_item` không kiểm tra tồn kho
Vá: khi cập nhật số lượng giỏ, nạp option và chặn `option.stock < quantity` -> E10201 (nhánh
tạo/tăng đã kiểm tra từ trước).

### #5 (trung bình) Mã lỗi sai
- `cart_controller.detail`: giỏ không tồn tại `E10601` (403) -> `E10300` (404).
- `product_service.update_product`: danh mục không tồn tại `E10300` -> `E10202` (404).

### #6 (trung bình) Thiếu chống brute-force/spam -> rate limit qua CacheService

> ⚠ **Đã thay backend ngày 2026-08-21 (Xime 0.8):** bộ đếm chuyển từ `CacheService` sang
> `RateLimitStore` (`CounterStore` trên LMDB) - dùng chung giữa các tiến trình của một máy và
> `incr()` nguyên tử. Ngưỡng, khóa và mã lỗi bên dưới **giữ nguyên**. Lý do và phép đo:
> [`nang-cap-xime-0.8.md`](nang-cap-xime-0.8.md#22-hãm-nhịp-chuyển-sang-xime-store-lmdb).

Quyết định người dùng khi đó: **dùng CacheService**. `RateLimiterService` (đếm theo key + TTL,
InMemoryCache đổi Redis được):
- `/login`: tối đa 5 lần SAI/username/15 phút (đếm khi sai, reset khi đúng) -> 429 `E2003`.
- `/forgot-password`: 3 lần/email/15 phút -> 429 `E1040`.
- `/otp/request`: 3 lần/user/15 phút -> 429 `E1040`.
- Khóa theo tài khoản mục tiêu (không theo IP) vì lưu lượng qua proxy Next.js nên IP không phân
  biệt được người gọi.

## Cải thiện thêm (Part B, 2026-07-01)

- **Đổi mật khẩu + đăng xuất các phiên khác:** `ChangePasswordRequest.logoutOtherSessions` (nút
  tích, mặc định False). Khi True: thu hồi refresh token của MỌI phiên khác nhưng GIỮ phiên hiện
  tại (`refresh_svc.delete_by_user_except(user.id, keep_jti)` với `keep_jti` = `refreshId` của
  access token đang dùng). Phiên khác chết ở lần refresh kế (access token còn hiệu lực tối đa
  `access_ttl` = 1h). Test: `test_change_password_logout_other_sessions_keeps_current`.
- **Danh sách user (admin) đổi sang NEWEST-FIRST** (`user_repository.find_all_paginated` order
  `id.desc()`) cho nhất quán với orders/files và để user mới đăng ký hiện ở trang 1 (trước đây asc
  nên khi >100 user thì user mới không thấy ở trang 1).

## Nhóm 🟡 nhẹ - ĐÃ LÀM NỐT (Part C, 2026-07-01)

- **#8 Chống dò tài khoản + timing (login):** `verify_user_password` trả CÙNG lỗi `E1005` cho cả
  username không tồn tại lẫn sai mật khẩu, và luôn chạy một phép bcrypt (verify với `_DUMMY_HASH`
  khi user không tồn tại) để thời gian phản hồi đồng nhất. Test:
  `test_login_unknown_username_returns_generic_e1005`.
- **#9 Tiền dùng Decimal:** thêm `app/money.py` (`money()`, `quantize()` ROUND_HALF_UP 2dp).
  `pricing.py` + `coupon_service.compute_discount` + pipeline tính tiền trong `order_service`
  (subtotal/discount/total) chuyển sang Decimal; gán thẳng vào cột Numeric (không qua float). DTO
  trả JSON vẫn convert `float(...)` ở biên. Test: `test_compute_discount_uses_decimal_precision`.
- **#10 `/logout` thêm POST** (chuẩn REST) nhưng GIỮ GET để không phá frontend đang gọi GET
  (dùng chung `_logout`). Test: `test_logout_supports_post`.
- **#11 `broadcast` chèn theo lô** (`repo.save_all([...])`) thay vì save() từng cái.
- **#12 Đổi tồn kho làm mới cache sản phẩm:** `ProductService.invalidate_cache(product_id)` (public);
  `OrderService` inject `ProductService` và gọi khi đặt đơn (`create_order`) hoặc hoàn kho
  (`expire_overdue_online_orders`) -> `GET /products` không hiển thị tồn kho cũ. Test:
  `test_stock_change_invalidates_product_cache`.

Tổng: **166 test pass**. Không còn mục tồn đọng đã biết từ đợt rà soát này.
