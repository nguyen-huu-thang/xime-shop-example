# Issue #5 — Thêm starter gửi email (SMTP) cho Xime

> ✅ **ĐÃ GIẢI QUYẾT PHÍA FRAMEWORK (Xime 0.6.2, 2026-06-30).** Đã có `xime.starters.mail`:
> Protocol `MailService` + `SmtpMailService` (aiosmtplib, đọc `mail.*`, fail-fast thiếu
> `mail.smtp.host`, STARTTLS 587 / TLS 465, timeout), `EmailMessage`, `MailError`/`MailSendError`.
> Extra `xime[mail]` = `aiosmtplib>=3.0`. 17 test starter pass.
>
> ✅ **Shop đã tích hợp hạ tầng (2026-06-30):** `scan("xime.starters.mail")` +
> `bind({MailService: SmtpMailService})`; `mail.*` trong application.yml (host sẵn, username/password
> chờ điền); app-level `EmailService` (tự TẮT khi chưa cấu hình); email xác nhận đơn + thanh toán
> (nền); endpoint test `GET/POST /api/email/*`. Chi tiết: [`../docs/thiet-ke-email.md`](../docs/thiet-ke-email.md).
> Còn lại (chưa code): email bảo mật OTP/reset/verify - xem Phase C/D/E trong doc.

- **Mức độ:** Trung bình (đề xuất tính năng mới - starter)
- **Phase phát hiện:** Pha hoàn thiện backend (thiết kế checkout + email cho shop)
- **Thành phần đề xuất:** starter mới `xime.starters.mail` (tên có thể đổi: `mail` / `email` / `smtp`)
- **Liên quan:** khuôn mẫu starter sẵn có (`storage`, `cache`) - Protocol + backend cụ thể + bind trong `config/dependency.py`; cấu hình qua `RuntimeConfig`.
- **Trạng thái:** CHỜ FRAMEWORK LÀM. Shop sẽ code phần email sau khi starter sẵn sàng (làm một thể).

## Bối cảnh & nhu cầu

Dự án shop cần **gửi email thật** (qua Gmail cá nhân, SMTP + app password) cho 2 nhóm:

1. **Email bảo mật, gửi ĐỒNG BỘ** (người dùng đang chờ realtime): OTP, reset mật khẩu, xác minh email.
   - Cần biết NGAY gửi thành công hay thất bại để báo lại người dùng -> phải `await` được kết quả +
     có timeout + ném lỗi rõ khi fail.
2. **Email giao dịch, gửi NỀN** (người dùng không chờ): xác nhận đơn hàng, đổi trạng thái giao.
   - Không được làm chậm / không được làm hỏng nghiệp vụ chính (đơn đã tạo xong rồi). Lỗi gửi chỉ log.

Xime hiện **không có starter email nào** (`xime/starters/` chỉ có cache, jwt, localfs, redis, s3,
scheduler, sqlalchemy, storage). Mỗi app tự viết `smtplib`/`aiosmtplib` -> đúng kiểu boilerplate hạ
tầng mà framework nên gánh, giống cách `storage` gánh việc lưu file.

## Đề xuất API (khớp khuôn mẫu starter hiện có)

Theo đúng pattern `storage`/`cache`: **một Protocol interface** + **một backend SMTP cụ thể**, app
bind trong `config/dependency.py`. Tầng service chỉ phụ thuộc Protocol -> sau này đổi nhà cung cấp
(SMTP -> SendGrid/SES API) chỉ sửa 1 dòng bind.

### 1. Protocol `MailService` (interface)

```python
# xime/starters/mail/_service.py
from typing import Protocol, Sequence

class EmailMessage:
    to: Sequence[str]
    subject: str
    html: str | None
    text: str | None
    cc: Sequence[str] | None
    reply_to: str | None
    # from lấy từ config mail.from mặc định, cho override nếu cần

class MailService(Protocol):
    async def send(self, message: EmailMessage) -> None:
        """Gửi email, AWAIT tới khi xong (đồng bộ về mặt logic).
        Thành công -> return; thất bại -> raise MailSendError. Có timeout nội bộ.
        """
        ...
```

- `send()` là **awaitable** và phản ánh đúng kết quả: đây là cái dùng cho email bảo mật (đồng bộ).
  App `await mail.send(...)` trong request handler, bắt `MailSendError` -> trả `AppException` sạch.
- **Gửi nền là việc điều phối của app, KHÔNG nhét vào starter.** App tự quyết: muốn nền thì bọc
  `send()` trong `asyncio.create_task(...)` / FastAPI `BackgroundTasks` / scheduler. Như vậy starter
  giữ tối giản, không ôm hàng đợi. (Nếu sau này muốn, có thể bổ sung helper `send_in_background`
  hoặc tích hợp scheduler, nhưng KHÔNG cần cho bản đầu.)

### 2. Backend SMTP cụ thể `SmtpMailService`

```python
# xime/starters/mail/_smtp.py
class SmtpMailService:   # implements MailService
    def __init__(self, config: RuntimeConfig) -> None:
        # đọc mail.smtp.* qua RuntimeConfig (giống LocalFileStorage đọc storage.local.root)
        ...
    async def send(self, message: EmailMessage) -> None:
        # dùng aiosmtplib (async, không chặn event loop) + timeout từ config
        ...
```

- Nên dùng **`aiosmtplib`** (async) thay vì `smtplib` thuần (đồng bộ, chặn event loop). Nếu muốn
  tránh thêm dependency, có thể chạy `smtplib` trong `asyncio.to_thread`, nhưng `aiosmtplib` sạch hơn.
- `__init__.py` của starter để `__all__ = ["SmtpMailService"]` (đăng ký backend cụ thể vào DI khi
  scan); Protocol `MailService` import được trực tiếp cho bind + type hint (giống `storage`).

### 3. Cách app dùng (dự kiến trong shop)

```python
# config/dependency.py
from xime.starters.mail import MailService, SmtpMailService
dependency.scan(..., "xime.starters.mail")
dependency.bind({ MailService: SmtpMailService })

# service bảo mật (đồng bộ): await + bắt lỗi
await self._mail.send(EmailMessage(to=[user.email], subject="Mã OTP", html=...))

# service giao dịch (nền): không chặn đặt hàng, lỗi chỉ log
asyncio.create_task(self._mail.send(EmailMessage(to=[user.email], subject="Xác nhận đơn", html=...)))
```

## Cấu hình đề xuất (resources/application.yml)

```yaml
mail:
  from: "Shop Demo <your.email@gmail.com>"
  smtp:
    host: smtp.gmail.com
    port: 587
    username: your.email@gmail.com
    password: ""          # app password - tiêm lúc runtime, KHÔNG commit (xem issue-004)
    use_tls: true         # STARTTLS cho port 587 (hoặc ssl cho 465)
    timeout: 10           # giây - quan trọng cho email đồng bộ, tránh treo request
```

> Mật khẩu app password là secret -> không commit; nạp lúc runtime. Liên quan trực tiếp
> [issue-004](issue-004-ho-tro-env-var-cau-hinh.md) (cấu hình qua env var / mount file). Bản đầu chỉ
> cần đọc từ yml là đủ chạy; secret xử lý theo workaround mount file của issue-004.

## Exception

- `MailError` (base), `MailSendError` (gửi thất bại: SMTP từ chối, timeout, mất kết nối). App map
  sang `AppException` của mình. Theo mẫu `storage._exceptions` (`StorageError`, `ObjectNotFound`...).

## Phạm vi tối giản cho bản đầu (đủ cho shop)

Cần: `send()` async + timeout + `MailSendError`, hỗ trợ HTML + text, nhiều người nhận, `from` mặc
định từ config, backend SMTP (Gmail STARTTLS 587). 

CHƯA cần (để sau nếu có nhu cầu): template engine, hàng đợi/retry tích hợp, đính kèm file, nhiều
provider API (SendGrid/SES), bulk/marketing. Template HTML shop sẽ tự render ở tầng app.

## Tại sao để framework gánh (không tự viết trong shop)

- Cùng lý do với storage/cache: hạ tầng gửi email lặp lại ở mọi app nhóm Monolithic (shop,
  dental-clinic, auto-garage, english-center, rental-management, spa).
- Giữ tầng service của app phụ thuộc Protocol -> đổi nhà cung cấp không đụng nghiệp vụ.
- Đồng nhất cấu hình (`mail.*`) + xử lý lỗi giữa các app.

## Việc shop sẽ làm sau khi starter sẵn sàng

1. `scan("xime.starters.mail")` + `bind({ MailService: SmtpMailService })`, thêm `mail.*` vào yml.
2. Nối `notification_service` (chỗ hiện chỉ `logger.info`, [`notification_service.py`](../../app/service/notification_service.py)) sang gửi thật khi `type == "email"`.
3. Thiết kế + code các luồng email theo [`docs/thiet-ke-email.md`](../docs/thiet-ke-email.md) (sẽ viết):
   - Đồng bộ: OTP / reset mật khẩu / xác minh email.
   - Nền: xác nhận đơn (móc sau tạo đơn COD / sau callback thanh toán online thành công của
     [`docs/thiet-ke-checkout.md`](../docs/thiet-ke-checkout.md)).
