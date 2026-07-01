# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mục tiêu dự án

Migrate shop backend từ **PHP/Symfony** (`D:\code\PHP\shop-backend`) sang **Python**, dùng framework
**Xime** (`D:\code\xime\xime framework`). Giữ **kiến trúc đa lớp** của bản gốc (KHÔNG dùng Hexagonal
như Xime khuyến nghị).

## 📂 Toàn bộ thiết kế & kế hoạch nằm trong `.claude/`

> **Bắt đầu phiên làm việc: đọc [`.claude/CLAUDE.md`](.claude/CLAUDE.md)** — đây là điểm vào của mọi
> tài liệu (kiến trúc, kế hoạch theo phase, quy tắc code, mapping PHP→Python).

Bản đồ nhanh:

| Cần gì | Đọc |
|---|---|
| Điểm vào / mục lục | [`.claude/CLAUDE.md`](.claude/CLAUDE.md) |
| **Kiến trúc đa lớp + lý do không Hexagonal** | [`.claude/docs/kien-truc-da-lop.md`](.claude/docs/kien-truc-da-lop.md) |
| Cây thư mục Python | [`.claude/docs/cay-thu-muc.md`](.claude/docs/cay-thu-muc.md) |
| **Kế hoạch migrate (10 phase)** | [`.claude/docs/ke-hoach/README.md`](.claude/docs/ke-hoach/README.md) |
| Quy tắc code | [`.claude/rules/coding-da-lop.md`](.claude/rules/coding-da-lop.md) |
| Domain model (schema CSDL) | [`.claude/docs/domain-model.md`](.claude/docs/domain-model.md) |
| Mapping PHP → Python | [`.claude/docs/mapping-php-python.md`](.claude/docs/mapping-php-python.md) |
| Phân quyền / Error code / JWT | [`.claude/docs/phan-quyen.md`](.claude/docs/phan-quyen.md), [`error-code-system.md`](.claude/docs/error-code-system.md), [`auth-jwt.md`](.claude/docs/auth-jwt.md) |

## Nguồn & đích

| | Đường dẫn |
|---|---|
| Nguồn PHP | `D:\code\PHP\shop-backend\src\` |
| Đích Python | `d:\code\PYTHON\xime\shop\app\` |
| Framework Xime | `D:\code\xime\xime framework\` |
| App mẫu dùng Xime | `D:\code\xime\Base Platform\data\app\` |

## Cách chạy (khi đã có code)

```bash
python app/main.py        # hoặc: python -m app.main
```

Framework tự thêm `./app` vào `sys.path`.

## Trạng thái hiện tại

**Đã hoàn thiện migrate (Phase 0-9)** và đang ở **pha tối ưu**: app chạy được, đầy đủ
controller/service/repository/entity, test pass. Các cải tiến đã làm sau migrate:

- Auth: refresh token chuyển sang **httpOnly cookie path-scoped** (`/api/refresh-token`),
  access token trả body; `/refresh-token` xoay refresh token (rotation).
- `JwtMiddleware` chuyển sang **pure-ASGI** (sửa rò identity giữa request).
- `order_service` + `product_service`: gộp transaction, bỏ N+1; thêm `OrderResponse` DTO.
- **Storage starter** (localfs) cho upload + endpoint stream `/media/{key}` (HTTP Range).
- **Cache** catalog (InMemoryCacheService, đổi sang Redis được) + invalidation.
- **Dashboard** thống kê: `GET /api/dashboard/stats`.
- Vá bug: thiếu quyền `view_files`/`delete_file` trong seed.
- **Gỡ `ShopWebAdapter` tự viết** -> dùng API `configure_cors` / `configure_middleware` /
  `configure_exception_handlers` của Xime trong `app/config/web.py`; `main.py` chỉ còn `WebAdapter()`.
  Chi tiết wiring web layer: [`.claude/docs/go-web-adapter-dung-configure.md`](.claude/docs/go-web-adapter-dung-configure.md).
- **Tối ưu N+1 Product/Variant:** index FK + UNIQUE (migration `c3e4a5b6d7f8`); batch query gỡ N+1
  trong dựng DTO sản phẩm (`ProductService._to_dtos`) và `find_product_option_by_json`. Chi tiết:
  [`.claude/docs/toi-uu-product-variant.md`](.claude/docs/toi-uu-product-variant.md).
- **Cá nhân hóa người dùng (không AI):** kho sự kiện có trọng số (Action/Interaction) + affinity
  category materialized decay-on-write + co-occurrence đồng mua. Endpoint `recently-viewed`/`trending`/
  `for-you`/`products/{id}/related`. Migration `d4f5a6b7c8e9`..`f6a7b8c9d0e1`. Xime scheduler dựng lại
  co-occurrence hằng ngày 03:00 (gate bỏ qua khi test); kèm endpoint admin thủ công. Chi tiết:
  [`.claude/docs/ca-nhan-hoa-nguoi-dung.md`](.claude/docs/ca-nhan-hoa-nguoi-dung.md).
- **Checkout (demo) - đã code, 135 test pass:** sổ địa chỉ `user_addresses` (+ tọa độ lat/lng),
  coupon nâng cấp (loại %/số tiền + trần, đơn tối thiểu, scope SP/ship, giới hạn lượt dùng,
  per_user_once), tính tiền + endpoint `POST /api/orders/preview`, tạo đơn theo `addressId` +
  `couponCode` + `paymentProvider` (nối đầy đủ ship + coupon vào `total_amount`), thanh toán giả lập
  (`POST /api/orders/{id}/pay` + `POST /api/payments/mock/callback`). Migration `a7b8c9d0e1f2`..
  `d0e1f2a3b4c5`. Chi tiết: [`.claude/docs/thiet-ke-checkout.md`](.claude/docs/thiet-ke-checkout.md).
- **Thông báo in-app - đã code:** hộp thư theo user (`/api/notifications/me`, `/me/unread-count`,
  `/me/read-all`), vá IDOR `PATCH /{id}/read` (owner-only), helper `notify()` tự sinh khi đặt hàng /
  thanh toán thành công / đổi trạng thái giao, admin broadcast (`POST /api/notifications/broadcast`).
  Chi tiết: [`.claude/docs/thiet-ke-thong-bao.md`](.claude/docs/thiet-ke-thong-bao.md).
- **Email - đã code (hạ tầng + giao dịch + bảo mật), 146 test pass:** bind `MailService: SmtpMailService`
  (`xime.starters.mail`) + `mail.*` trong application.yml (host sẵn, **username/password chờ điền**
  Gmail app password); `EmailService` tự TẮT khi chưa cấu hình; email xác nhận đơn + thanh toán (nền);
  endpoint test admin `GET/POST /api/email/*`. **Email bảo mật**: bảng chung `auth_tokens` +
  `AuthTokenService` (verify 24h/reset 30p/OTP 5p, lưu hash); xác minh email (`/api/verify-email`
  [+resend], cột `users.email_verified`, hook khi register), quên/đặt lại mật khẩu (`/api/forgot-password`
  + `/api/reset-password`, thu hồi mọi refresh token qua `refresh_tokens.user_id` - CHỈ khi reset),
  OTP (`/api/otp/request` + `/api/otp/verify`, chưa wire vào login). Migration `e1f2a3b4c5d6`. Còn lại:
  Phase B (kênh email cho notify). Chi tiết: [`.claude/docs/thiet-ke-email.md`](.claude/docs/thiet-ke-email.md).
- **Rà soát & vá phân quyền (2026-06-30) - đã xong:** vá `search_controller` (users/groups cần quyền
  admin; cart/orders cần đăng nhập), `review_controller` (create gán userId theo user đăng nhập;
  update chỉ chủ sở hữu - vá IDOR; detail không lộ review chưa duyệt). `/media/{key}` giữ công khai
  có chủ đích (ảnh sản phẩm). Test regression `test/test_security.py`. Chi tiết:
  [`.claude/docs/audit-phan-quyen-2026-06-30.md`](.claude/docs/audit-phan-quyen-2026-06-30.md).
- **Rà soát backend + vá lỗi (2026-07-01) - đã xong, 166 test pass:** khóa tồn kho/coupon chống
  race (`SELECT FOR UPDATE`), kẹp phân trang (`app/pagination.py`) chống 500 do offset âm, **giữ
  chỗ tồn kho kiểu Shopee** (mọi đơn trừ kho ngay lúc đặt; đơn online có hạn 1 ngày, quá hạn
  `ExpireOrdersJob` hoàn kho + hủy đơn; cột `order_details.product_option_id` +
  `orders.payment_deadline/cancelled_at`, migration `f7b8c9d0e1a2` + `a8c9d0e1f2b3`), kiểm tra tồn
  kho khi sửa giỏ, sửa mã lỗi sai (cart/product), rate limit login/forgot-password/otp qua
  CacheService (`RateLimiterService`), đổi mật khẩu kèm tùy chọn đăng xuất phiên khác (giữ phiên
  hiện tại), danh sách user admin newest-first. **Nhóm nhẹ:** chống dò tài khoản + timing khi
  login (E1005 chung + bcrypt giả), tiền tính bằng Decimal (`app/money.py`), thêm `POST /logout`
  (giữ GET), `broadcast` bulk insert, đổi tồn kho làm mới cache DTO sản phẩm. Test regression
  `test/test_hardening.py`. Chi tiết:
  [`.claude/docs/ra-soat-backend-2026-07-01.md`](.claude/docs/ra-soat-backend-2026-07-01.md).


## framework issues

nếu framework có bất kì vấn đề gì hãy ghi lại vào .claude\framework-issues
đọc .claude\framework-issues\README.md