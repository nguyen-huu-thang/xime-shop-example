"""
EmailService - lớp email cấp ứng dụng, bọc MailService của framework (xime.starters.mail).

Quy tắc gửi (xem .claude/docs/thiet-ke-email.md):
- Email bảo mật (OTP, reset mật khẩu, xác minh email): gửi ĐỒNG BỘ qua `send()` - await kết
  quả, lỗi ném ra để báo người dùng.
- Email giao dịch (xác nhận đơn, đổi trạng thái giao): gửi NỀN qua `send_in_background()` -
  fault-tolerant, lỗi chỉ log, KHÔNG làm hỏng nghiệp vụ chính.

Tự TẮT khi chưa cấu hình SMTP (thiếu mail.smtp.username/password) -> bỏ qua gửi, chỉ log. Nhờ vậy
chạy test / chạy dev khi chưa điền Gmail vẫn không gọi mạng và không lỗi.
"""
from __future__ import annotations

import asyncio
import logging

from xime.core.config.runtime import RuntimeConfig
from xime.starters.mail import EmailMessage, MailError, MailService

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, mail: MailService, config: RuntimeConfig) -> None:
        self._mail = mail
        # Bật gửi chỉ khi đã điền đủ username + password (Gmail app password)
        # Enabled only when both username and password are configured
        self._enabled = bool(
            config.get("mail.smtp.username") and config.get("mail.smtp.password")
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send(self, message: EmailMessage) -> None:
        """Gửi đồng bộ - await tới khi xong, raise MailSendError nếu lỗi.

        Dùng cho email bảo mật (OTP/reset/verify) và endpoint test thủ công.
        Nếu chưa cấu hình SMTP -> raise MailError để caller biết rõ.
        """
        if not self._enabled:
            raise MailError(
                "SMTP chưa cấu hình (điền mail.smtp.username/password trong application.yml)"
            )
        await self._mail.send(message)

    async def send_safe(self, message: EmailMessage) -> bool:
        """Gửi fault-tolerant - không bao giờ raise. Trả True nếu đã gửi, False nếu bỏ qua/lỗi.

        Dùng cho email giao dịch chạy nền (lỗi không được làm hỏng nghiệp vụ chính).
        """
        if not self._enabled:
            logger.info("Email đang TẮT (chưa cấu hình SMTP) - bỏ qua: %s", message.subject)
            return False
        try:
            await self._mail.send(message)
            return True
        except MailError:
            logger.exception("Gửi email thất bại: %s", message.subject)
            return False

    def send_in_background(self, message: EmailMessage) -> None:
        """Lên lịch gửi nền (không chặn request). Lỗi được nuốt trong send_safe."""
        # asyncio.create_task chạy trong event loop của ASGI; giữ tham chiếu tránh GC sớm
        task = asyncio.create_task(self._send_safe_bg(message))
        _BG_TASKS.add(task)
        task.add_done_callback(_BG_TASKS.discard)

    async def _send_safe_bg(self, message: EmailMessage) -> None:
        await self.send_safe(message)

    # ── Builders cho từng loại email (demo: HTML đơn giản inline) ────────────────

    async def send_order_confirmation(
        self, to_email: str, order_id: int, total_amount: float
    ) -> None:
        """Email xác nhận đơn (giao dịch -> gửi NỀN)."""
        if not to_email:
            return
        html = (
            f"<h2>Cảm ơn bạn đã đặt hàng!</h2>"
            f"<p>Đơn hàng <b>#{order_id}</b> của bạn đã được tạo thành công.</p>"
            f"<p>Tổng tiền: <b>{total_amount:,.0f} đ</b></p>"
            f"<p>Chúng tôi sẽ thông báo khi đơn được giao.</p>"
        )
        self.send_in_background(
            EmailMessage(
                to=[to_email],
                subject=f"Xác nhận đơn hàng #{order_id}",
                html=html,
            )
        )

    async def send_notification(
        self, to_email: str, title: str, message: str | None = None, link: str | None = None
    ) -> None:
        """Email thông báo chung (kèm theo thông báo in-app). Gửi NỀN, fault-tolerant.

        Dùng cho Phase B - cờ also_email của NotificationService.notify().
        """
        if not to_email:
            return
        html = f"<h2>{title}</h2>"
        if message:
            html += f"<p>{message}</p>"
        if link:
            html += f"<p><a href='{link}'>{link}</a></p>"
        self.send_in_background(
            EmailMessage(to=[to_email], subject=title, html=html)
        )

    # ── Email bảo mật (gửi ĐỒNG BỘ - người dùng đang chờ; raise nếu lỗi) ──────────

    async def send_verify_email(self, to_email: str, token: str) -> None:
        """Email xác minh tài khoản. Gửi đồng bộ (raise MailError nếu lỗi/chưa cấu hình)."""
        link = f"/verify-email?token={token}"
        html = (
            "<h2>Xác minh email</h2>"
            "<p>Nhấn vào liên kết sau để xác minh email của bạn (hết hạn sau 24 giờ):</p>"
            f"<p><a href='{link}'>{link}</a></p>"
        )
        await self.send(
            EmailMessage(to=[to_email], subject="Xác minh email", html=html)
        )

    async def send_reset_password(self, to_email: str, token: str) -> None:
        """Email đặt lại mật khẩu. Gửi đồng bộ."""
        link = f"/reset-password?token={token}"
        html = (
            "<h2>Đặt lại mật khẩu</h2>"
            "<p>Bạn (hoặc ai đó) đã yêu cầu đặt lại mật khẩu. Liên kết hết hạn sau 30 phút:</p>"
            f"<p><a href='{link}'>{link}</a></p>"
            "<p>Nếu không phải bạn, hãy bỏ qua email này.</p>"
        )
        await self.send(
            EmailMessage(to=[to_email], subject="Đặt lại mật khẩu", html=html)
        )

    async def send_otp(self, to_email: str, code: str) -> None:
        """Email mã OTP. Gửi đồng bộ."""
        html = (
            "<h2>Mã xác thực (OTP)</h2>"
            f"<p>Mã của bạn là: <b style='font-size:20px'>{code}</b></p>"
            "<p>Mã hết hạn sau 5 phút. Không chia sẻ mã này với bất kỳ ai.</p>"
        )
        await self.send(
            EmailMessage(to=[to_email], subject="Mã OTP đăng nhập", html=html, text=f"OTP: {code}")
        )

    async def send_payment_success(
        self, to_email: str, order_id: int
    ) -> None:
        """Email báo thanh toán thành công (giao dịch -> gửi NỀN)."""
        if not to_email:
            return
        html = (
            f"<h2>Thanh toán thành công</h2>"
            f"<p>Đơn hàng <b>#{order_id}</b> đã được thanh toán. Cảm ơn bạn!</p>"
        )
        self.send_in_background(
            EmailMessage(
                to=[to_email],
                subject=f"Đã thanh toán đơn hàng #{order_id}",
                html=html,
            )
        )


# Giữ tham chiếu các task nền để event loop không thu gom giữa chừng
# Keep references to background tasks so the loop doesn't GC them mid-flight
_BG_TASKS: set[asyncio.Task] = set()
