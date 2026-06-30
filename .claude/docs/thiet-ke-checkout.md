# Thiết kế Checkout / Thanh toán (demo)

> Trạng thái: ĐANG THIẾT KẾ (2026-06-30). Chưa code.
> Liên quan: [`domain-model.md`](domain-model.md), [`order_service.py`](../../app/service/order_service.py),
> [`coupon_service.py`](../../app/service/coupon_service.py). Phần email tách riêng:
> [`thiet-ke-email.md`](thiet-ke-email.md) (làm sau).

## 1. Mục tiêu & phạm vi

Hoàn thiện luồng checkout cho website shop **ở mức demo cho đẹp**, không tích hợp cổng thanh toán
thật, không gửi tiền thật. Bối cảnh: **một bên bán** (cửa hàng demo của chủ dự án) và **nhiều bên
mua** (khách vãng lai). Không phải marketplace nhiều người bán.

Luồng tổng thể:

```
Giỏ hàng -> Chọn/nhập địa chỉ giao (có tọa độ) -> Áp coupon + tính phí ship
         -> Chọn phương thức thanh toán -> Tạo đơn -> [COD] hoặc [Cổng online giả lập]
         -> Xác nhận đơn -> (Email xác nhận: doc riêng)
```

## 2. Quyết định đã chốt (2026-06-30)

| Vấn đề | Lựa chọn |
|---|---|
| Phương thức thanh toán | **COD + cổng online giả lập** (redirect -> bấm thành công -> callback set đã thanh toán) |
| Địa chỉ giao + tọa độ | **Sổ địa chỉ riêng** (`user_addresses`) + order snapshot lại lúc đặt; tọa độ `lat`/`lng` |
| Coupon + phí ship | **Nối đầy đủ** vào `total_amount` (tận dụng cột `shipping_fee`/`product_discount`/`ship_discount`/`coupon_id` đã có trong `Order`) |
| Nâng cấp coupon | Loại giảm **% / số tiền** (+ trần giảm), **đơn tối thiểu**, **scope SP/ship**, **giới hạn lượt dùng** |
| Bản đồ hiển thị tọa độ (FE) | **Leaflet + OpenStreetMap** (miễn phí, không cần API key) |

## 3. Thay đổi schema

### 3.1. Bảng mới: `user_addresses` (sổ địa chỉ)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | BigInteger PK | |
| user_id | BigInteger FK users | chủ sổ địa chỉ |
| recipient_name | String(100) | tên người nhận |
| recipient_phone | String(20) | SĐT người nhận |
| province | String(100) | tỉnh/thành |
| district | String(100) | quận/huyện |
| ward | String(100) | phường/xã |
| detail | String(255) | số nhà, đường... |
| lat | Numeric(10,7) nullable | vĩ độ |
| lng | Numeric(10,7) nullable | kinh độ |
| is_default | Boolean default False | địa chỉ mặc định |
| created_at / updated_at | TimestampMixin | |

Quy tắc: mỗi user có tối đa 1 địa chỉ `is_default=True` (khi set default mới thì gỡ default cũ,
trong cùng 1 transaction).

### 3.2. Sửa bảng `orders` - thêm cột snapshot địa chỉ + thanh toán

Giữ cột `address` (String) cũ để tương thích, nhưng bổ sung snapshot có cấu trúc + tọa độ + trạng
thái thanh toán giả lập:

| Cột thêm | Kiểu | Ghi chú |
|---|---|---|
| recipient_name | String(100) nullable | snapshot lúc đặt |
| recipient_phone | String(20) nullable | snapshot |
| ship_lat | Numeric(10,7) nullable | tọa độ giao (snapshot) |
| ship_lng | Numeric(10,7) nullable | tọa độ giao (snapshot) |
| payment_provider | String(20) default "cod" | `cod` \| `mock_online` |
| payment_ref | String(64) nullable | mã giao dịch giả lập (uuid) cho cổng online |
| paid_at | DateTime nullable | thời điểm "thanh toán" |

`address` (String 255) tiếp tục lưu địa chỉ gộp dạng người-đọc (province + district + ward + detail)
để khỏi đổi chỗ đang hiển thị. `payment_status` (bool) giữ nguyên: COD -> False đến khi giao xong;
online giả lập -> True sau callback.

### 3.3. Sửa bảng `coupons` - nâng cấp

| Cột thêm/sửa | Kiểu | Ghi chú |
|---|---|---|
| discount_type | String(10) default "fixed" | `fixed` (số tiền) \| `percent` (%) |
| discount | Numeric(10,2) | giữ tên; nếu percent thì là số phần trăm (0-100), nếu fixed thì là số tiền |
| max_discount | Numeric(10,2) nullable | trần giảm khi `percent` (vd giảm 20% tối đa 100k) |
| min_order_amount | Numeric(10,2) default 0 | đơn tối thiểu để áp mã |
| applies_to | String(10) default "product" | `product` (giảm tiền hàng -> product_discount) \| `shipping` (giảm phí ship -> ship_discount) |
| usage_limit | Integer nullable | tổng số lượt dùng cho phép; null = không giới hạn |
| used_count | Integer default 0 | đã dùng bao nhiêu lượt |
| per_user_once | Boolean default False | mỗi user chỉ dùng 1 lần (đếm qua `orders.coupon_id` + `user_id`) |

> Per-user-once dùng cách nhẹ: đếm `orders` có cùng `coupon_id` + `user_id`, không cần bảng riêng.
> Đủ cho demo.

### 3.4. Migration

Một migration Alembic mới (revision nối tiếp đầu HEAD hiện tại) gồm: tạo `user_addresses`,
`ALTER TABLE orders ADD ...`, `ALTER TABLE coupons ADD ...`. Index: `user_addresses(user_id)`,
`orders(coupon_id)` (nếu chưa có).

## 4. Tính toán tiền (chốt công thức)

```
subtotal        = Σ (order_detail.price * quantity)            # tiền hàng
shipping_fee    = rule_phi_ship(subtotal, địa chỉ)             # xem 4.1
product_discount, ship_discount = apply_coupon(coupon, subtotal, shipping_fee)   # xem 4.2
total_amount    = subtotal + shipping_fee - product_discount - ship_discount
total_amount    = max(total_amount, 0)
```

### 4.1. Phí ship (demo, đơn giản, cấu hình được)

Quy tắc demo (đưa vào config/hằng số, không hardcode rải rác):
- Phí ship phẳng mặc định: **30.000đ**.
- Miễn phí ship khi `subtotal >= 500.000đ`.

(Không tính theo tọa độ thật cho demo; tọa độ chỉ để hiển thị bản đồ. Có thể mở rộng sau.)

### 4.2. Áp coupon

```
1. Tìm coupon theo code; chưa thấy -> E10400.
2. Kiểm tra is_active + start_date <= now <= end_date; sai -> E10401 (hết hạn) / E10402 (không hợp lệ).
3. subtotal < min_order_amount -> E10404 (chưa đạt đơn tối thiểu).
4. usage_limit không null và used_count >= usage_limit -> E10405 (hết lượt).
5. per_user_once và user đã có order dùng coupon này -> E10406 (đã dùng).
6. Tính số tiền giảm:
   - discount_type == fixed   -> giảm = discount
   - discount_type == percent -> giảm = base * discount / 100; nếu max_discount: giảm = min(giảm, max_discount)
   với base = subtotal nếu applies_to == product, = shipping_fee nếu applies_to == shipping.
7. applies_to == product   -> product_discount = min(giảm, subtotal)
   applies_to == shipping   -> ship_discount    = min(giảm, shipping_fee)
8. Khi đặt đơn thành công: used_count += 1 (trong cùng transaction tạo order).
```

Có endpoint "xem trước" áp coupon (không tạo đơn) để FE hiển thị tổng tiền realtime trước khi đặt.

## 5. API endpoints

### 5.1. Sổ địa chỉ (`/api/addresses`) - controller mới `AddressController`

| Method | Path | Mô tả | Quyền |
|---|---|---|---|
| GET | `/api/addresses` | địa chỉ của user hiện tại | đăng nhập |
| POST | `/api/addresses` | thêm địa chỉ | đăng nhập |
| PUT | `/api/addresses/{id}` | sửa (chỉ chủ sở hữu) | đăng nhập + owner |
| DELETE | `/api/addresses/{id}` | xóa (chỉ chủ sở hữu) | đăng nhập + owner |
| PUT | `/api/addresses/{id}/default` | đặt mặc định | đăng nhập + owner |

### 5.2. Checkout / order (mở rộng `OrderController` sẵn có)

| Method | Path | Mô tả |
|---|---|---|
| POST | `/api/orders/preview` | (mới) nhận cartIds + addressId + couponCode -> trả breakdown (subtotal, ship, discount, total). KHÔNG tạo đơn |
| POST | `/api/orders` | (sửa) tạo đơn từ cartIds + addressId + couponCode + paymentProvider; snapshot địa chỉ + tọa độ; áp coupon + ship |
| POST | `/api/orders/{id}/pay` | (mới) bắt đầu thanh toán cổng online giả lập -> trả `payment_ref` + URL trang mock |
| POST | `/api/payments/mock/callback` | (mới) callback giả lập: nhận `payment_ref` + `success` -> set payment_status/paid_at |

> COD: `POST /api/orders` với `paymentProvider=cod` là xong, không cần bước pay.
> Online giả lập: `POST /api/orders` (provider=mock_online, chưa trả tiền) -> `POST /{id}/pay`
> (FE chuyển sang trang mock) -> trang mock gọi `POST /api/payments/mock/callback`.

### 5.3. Coupon (mở rộng `CouponController` + service)

- `POST /api/coupons/apply` hoặc gộp vào `/api/orders/preview`: kiểm tra + tính giảm cho FE.
- Admin CRUD coupon cập nhật DTO theo cột mới (discount_type, max_discount, min_order_amount,
  applies_to, usage_limit, per_user_once).

## 6. DTO chính

- `AddressCreateRequest` / `AddressUpdateRequest` / `AddressResponse`.
- `OrderCreateRequest` (sửa): thêm `addressId: int`, `couponCode: str | None`,
  `paymentProvider: Literal["cod","mock_online"]`. Giữ `cartIds`. (Có thể vẫn cho `address` raw để
  tương thích, nhưng ưu tiên `addressId`.)
- `OrderPreviewRequest` / `OrderPreviewResponse` (breakdown tiền).
- `PaymentInitResponse` (payment_ref + mock_url).
- `MockPaymentCallbackRequest` (payment_ref, success).
- `CouponResponse` / `CouponCreateRequest` / `CouponUpdateRequest`: thêm field mới.

## 7. Error code mới (đề xuất, chưa trùng dải hiện có)

| Key | code | message | http |
|---|---|---|---|
| E10320 | 10320 | Không tìm thấy địa chỉ giao hàng | 404 |
| E10321 | 10321 | Địa chỉ giao hàng không hợp lệ | 400 |
| E10404 | 10404 | Đơn hàng chưa đạt giá trị tối thiểu để dùng mã | 400 |
| E10405 | 10405 | Mã giảm giá đã hết lượt sử dụng | 400 |
| E10406 | 10406 | Bạn đã sử dụng mã giảm giá này | 400 |
| E10507 | 10507 | Đơn hàng đã được thanh toán | 400 |
| E10508 | 10508 | Phương thức thanh toán không hợp lệ | 400 |
| E10509 | 10509 | Giao dịch thanh toán không hợp lệ hoặc đã xử lý | 400 |

## 8. Phân quyền

- Sổ địa chỉ: chỉ chủ sở hữu (owner check như order detail đã làm). Không cần permission admin riêng.
- Tạo đơn / thanh toán: user đăng nhập (đang là `require_login`).
- Callback mock: không cần auth nhưng phải khớp `payment_ref` đang `pending` -> tránh set bừa.
- Admin coupon: giữ permission coupon hiện có.

## 9. Kế hoạch theo phase (làm tuần tự, mỗi phase có test)

- [x] **Phase 1 - Sổ địa chỉ + tọa độ.** Entity `user_addresses`, repository, service, controller,
  DTO, migration, test CRUD + đặt default. (Độc lập, không đụng order.)
- [x] **Phase 2 - Coupon nâng cấp.** Thêm cột coupons + migration; sửa CouponService logic áp mã
  (`apply_coupon` thuần tính toán) + DTO admin; unit test các nhánh (percent/fixed, min, limit,
  per-user, scope).
- [x] **Phase 3 - Tính tiền checkout + preview.** Hàm tính `shipping_fee`, ghép `apply_coupon`;
  endpoint `POST /api/orders/preview`; test breakdown.
- [x] **Phase 4 - Tạo đơn dùng địa chỉ + coupon + ship.** Sửa `OrderCreateRequest` + `create_order`
  (snapshot địa chỉ/tọa độ, set shipping_fee/discount/coupon_id/total, tăng used_count); cột order
  mới + migration; test atomic (tồn kho + cart + coupon used_count cùng 1 transaction).
- [x] **Phase 5 - Thanh toán giả lập.** Cột payment_* (gộp migration Phase 4 nếu muốn);
  `POST /orders/{id}/pay` + `POST /payments/mock/callback`; test COD vs online (pending -> paid).
- [x] **Phase 6 - Error code + seed + dọn dẹp.** Thêm error code mới; cập nhật doc; cập nhật
  [`domain-model.md`](domain-model.md) cho schema mới.

> Email xác nhận đơn: nối ở cuối, thiết kế trong [`thiet-ke-email.md`](thiet-ke-email.md). Điểm móc:
> sau khi đơn tạo thành công (COD) hoặc sau callback thanh toán thành công (online).

## 10. Ghi chú demo (không làm quá)

- Cổng online "giả lập" chỉ là một endpoint + trang FE mock; không ký số, không HMAC như VNPay thật.
  Bảo vệ tối thiểu bằng `payment_ref` (uuid) phải đang `pending`.
- Tọa độ không dùng để tính phí ship; chỉ hiển thị bản đồ Leaflet. Có thể cho phép nhập tay lat/lng
  hoặc bấm chọn trên bản đồ ở FE.
- Phí ship + ngưỡng freeship để dạng hằng số cấu hình, dễ chỉnh.
