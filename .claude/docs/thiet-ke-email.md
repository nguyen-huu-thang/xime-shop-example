# Thiết kế Hệ thống Email

> Trạng thái: hạ tầng + email giao dịch + email bảo mật (OTP/reset/verify) ĐÃ CODE (2026-06-30).
> Còn lại: Phase B (kênh email cho notify). Email starter framework đã sẵn (`xime.starters.mail`, issue-005).
> Liên quan: [`thiet-ke-checkout.md`](thiet-ke-checkout.md), [`thiet-ke-thong-bao.md`](thiet-ke-thong-bao.md),
> [`auth-jwt.md`](auth-jwt.md).

## 1. Mục tiêu & phạm vi

Gửi email thật qua **Gmail cá nhân** (SMTP + app password) ở mức demo. Hai nhóm email với quy tắc
gửi khác nhau:

| Nhóm | Người dùng đang chờ? | Cách gửi | Loại email |
|---|---|---|---|
| Bảo mật | Có (realtime) | **Đồng bộ** (await + timeout + báo lỗi rõ) | OTP, reset mật khẩu, xác minh email |
| Giao dịch | Không | **Nền** (fault-tolerant, lỗi chỉ log) | Xác nhận đơn, thanh toán thành công, đổi trạng thái giao |

Nguyên tắc rút gọn: **chờ -> đồng bộ; không chờ -> nền**.

## 2. Kiến trúc

```
Controller/Service  ->  EmailService (app)  ->  MailService (framework Protocol)
                                                 └─ SmtpMailService (aiosmtplib, SMTP)
```

- **Framework** (`xime.starters.mail`): `MailService.send(EmailMessage)` (await, raise `MailSendError`),
  backend `SmtpMailService` đọc `mail.*` từ config, mỗi `send()` mở/đóng 1 kết nối, tự chọn
  STARTTLS(587)/TLS(465), timeout nội bộ.
- **App** ([`email_service.py`](../../app/service/email_service.py)) `EmailService` bọc `MailService`:
  - `send(msg)` - đồng bộ (cho email bảo mật + endpoint test); raise nếu lỗi/chưa cấu hình.
  - `send_safe(msg)` - fault-tolerant (không raise), trả True/False.
  - `send_in_background(msg)` - lên lịch `asyncio.create_task(send_safe(...))` cho email giao dịch.
  - Builders sẵn: `send_order_confirmation`, `send_payment_success`.
  - **Tự TẮT khi chưa cấu hình SMTP** (thiếu `mail.smtp.username/password`) -> bỏ qua gửi, chỉ log;
    nhờ vậy test/dev không gọi mạng và không lỗi khi chưa điền Gmail.

Bind: [`config/dependency.py`](../../app/config/dependency.py) `scan("xime.starters.mail")` +
`bind({MailService: SmtpMailService})`.

## 3. Cấu hình (CHỖ TRỐNG cho bạn điền)

Trong [`resources/application.yml`](../../resources/application.yml) đã có khối `mail:` với host/port
Gmail đặt sẵn; **username/password/from để trống** chờ điền:

```yaml
mail:
  from: ""                       # "Shop Demo <bạn@gmail.com>" - ĐIỀN
  smtp:
    host: "smtp.gmail.com"
    port: 587
    username: ""                 # "bạn@gmail.com" - ĐIỀN
    password: ""                 # Gmail App Password (16 ký tự) - ĐIỀN
    use_tls: true
    timeout: 10
```

> **Bảo mật:** KHÔNG commit app password thật. Nên điền vào `resources/application-local.yml`
> (đã gitignore) thay vì `application.yml`, hoặc mount lúc runtime. Lấy App Password tại
> Google Account -> Security -> 2-Step Verification -> App passwords (cần bật 2FA).

Khi `username` + `password` còn trống -> `EmailService.enabled = False` -> mọi email bị bỏ qua an toàn.

## 4. Đã code (email giao dịch + hạ tầng)

- `EmailService` (BẬT/TẮT theo config) + bind MailService.
- **Email xác nhận đơn**: gửi NỀN sau khi tạo đơn ([`order_controller.create`](../../app/controller/order_controller.py)).
- **Email thanh toán thành công**: gửi NỀN sau callback thanh toán ([`payment_controller`](../../app/controller/payment_controller.py)).
- **Endpoint test SMTP thủ công** (admin, quyền `manage_system_settings`):
  - `GET /api/email/status` -> `{enabled: bool}` (đã cấu hình chưa).
  - `POST /api/email/test` body `{to, subject?, message?}` -> gửi ĐỒNG BỘ, trả `{sent, error?}`.
- Test: [`test_email.py`](../../test/test_email.py) (5 unit test BẬT/TẮT, không gọi mạng).

### Cách test thủ công (sau khi điền Gmail)
1. Điền `mail.smtp.username/password` + `mail.from` (vào `application-local.yml`).
2. `pip install xime[mail]` nếu chưa có `aiosmtplib` (môi trường hiện tại đã có 5.1.1).
3. Đăng nhập admin, gọi `POST /api/email/test` với `{"to": "địa-chỉ-nhận@..."}` -> kiểm hộp thư.
4. Hoặc đặt một đơn hàng -> nhận email xác nhận.

## 5. Email bảo mật - THIẾT KẾ (chưa code)

Các tính năng này shop CHƯA có, cần thêm. Tất cả gửi **ĐỒNG BỘ** (`EmailService.send`, bắt
`MailSendError` -> `AppException` để báo người dùng).

### 5.1. Xác minh email (verify email) khi đăng ký
- Sinh token xác minh (uuid hoặc mã ngắn), lưu kèm hạn (vd 24h).
- Gửi email chứa link `/verify-email?token=...`.
- Endpoint `POST /api/verify-email` nhận token -> set `users.email_verified = true`.
- Schema: thêm cột `users.email_verified` (bool) + bảng/cột lưu token xác minh (hoặc tái dùng
  cơ chế token chung, xem 5.4).

### 5.2. Quên/Reset mật khẩu
- `POST /api/forgot-password` body `{email}` -> sinh token reset (hạn ngắn, vd 30 phút), gửi email
  link `/reset-password?token=...`. Trả 200 dù email không tồn tại (tránh dò tài khoản).
- `POST /api/reset-password` body `{token, newPassword}` -> kiểm token còn hạn + chưa dùng ->
  đổi mật khẩu (hash), vô hiệu token, (tùy chọn) thu hồi refresh token hiện có.

### 5.3. OTP (đăng nhập 2 bước / xác nhận hành động nhạy cảm)
- `POST /api/otp/request` -> sinh mã 6 số, hạn ngắn (vd 5 phút), giới hạn tần suất (rate limit),
  gửi email. Gửi ĐỒNG BỘ để báo gửi được hay không.
- `POST /api/otp/verify` body `{otp}` -> kiểm mã + hạn + số lần thử.

### 5.4. Lưu token/mã (đề xuất)
- Một bảng chung `auth_tokens` (hoặc tách): `id`, `user_id`, `type` (verify/reset/otp), `token_hash`
  (hash, không lưu thô), `expires_at`, `used_at`, `created_at`. Đếm số lần thử cho OTP.
- Hết hạn/đã dùng -> từ chối. Dọn định kỳ qua Xime scheduler (giống co-occurrence).

### 5.5. Mẫu email
- Demo: HTML inline đơn giản (như order confirmation). Nếu cần đẹp hơn -> tách template sau.

## 6. Phase

- [x] **Phase A - Hạ tầng email + giao dịch.** Bind MailService, config placeholders, `EmailService`
  (BẬT/TẮT), email xác nhận đơn + thanh toán, endpoint test, unit test. (ĐÃ CODE)
- [x] **Phase B - Kênh email cho thông báo (Phase 4 của thiet-ke-thong-bao).** (ĐÃ CODE) Cờ
  `also_email` (+ `email_to`) cho `notify()` -> tạo in-app + gửi email thông báo (nền,
  fault-tolerant); `EmailService.send_notification`. Đã wire vào sự kiện **đổi trạng thái giao
  hàng**. Email xác nhận đơn + thanh toán vẫn dùng builder riêng (nội dung giàu hơn).
- [x] **Phase C - Xác minh email khi đăng ký.** (ĐÃ CODE) Cột `users.email_verified`; gửi email
  xác minh khi `/api/register` (fault-tolerant); `POST /api/verify-email` (token) + `POST
  /api/verify-email/resend` (đăng nhập). KHÔNG chặn đăng nhập nếu chưa xác minh (demo).
- [x] **Phase D - Quên/Reset mật khẩu.** (ĐÃ CODE) `POST /api/forgot-password` (luôn 200, chống dò
  tài khoản) + `POST /api/reset-password` (token, newPassword). Reset **thu hồi MỌI refresh token**
  của user (thêm `refresh_tokens.user_id` + `delete_by_user`). Đổi mật khẩu thường (biết mật khẩu
  cũ, `/change-password`) KHÔNG đụng email và KHÔNG thu hồi refresh token.
- [x] **Phase E - OTP.** (ĐÃ CODE) `POST /api/otp/request` (đăng nhập, gửi mã 6 số 5 phút) + `POST
  /api/otp/verify` (đếm số lần thử, tối đa 5). OTP gửi tới email user; **chưa wire vào luồng login**
  (là cặp request/verify độc lập, có thể gắn vào hành động nhạy cảm sau).

> Đã chốt (2026-06-30): **một bảng `auth_tokens` chung** (verify_email/reset_password/otp, lưu hash);
> TTL verify 24h / reset 30 phút / OTP 5 phút; chỉ thu hồi refresh token khi **reset qua quên mật
> khẩu** (không thu hồi khi đổi mật khẩu thường). Token quản lý bởi
> [`auth_token_service.py`](../../app/service/auth_token_service.py). Test: [`test_auth_email.py`](../../test/test_auth_email.py) (6 test).

## 7. Ghi chú demo (không làm quá)

- SMTP mở/đóng kết nối mỗi lần gửi (đủ cho lượng demo); không pool, không hàng đợi/retry.
- Email giao dịch chạy nền fault-tolerant: lỗi gửi KHÔNG làm hỏng đặt hàng/thanh toán.
- Email bảo mật đồng bộ + timeout: báo lỗi rõ cho người dùng đang chờ.
