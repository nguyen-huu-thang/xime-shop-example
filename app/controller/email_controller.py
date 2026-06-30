from __future__ import annotations

from xime.adapters.web.routing import get, post
from xime.starters.mail import EmailMessage, MailError

from app.dto.request.email_request import EmailTestRequest
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.email_service import EmailService


class EmailController:
    """Tiện ích email cho admin: kiểm tra trạng thái cấu hình + gửi email thử (test SMTP).

    Phục vụ test thủ công sau khi điền Gmail vào application.yml. Gửi ĐỒNG BỘ để báo
    ngay thành công/thất bại.
    """

    prefix = "/api/email"
    tags = ["email"]

    def __init__(
        self,
        email_service: EmailService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._email = email_service
        self._authz = authorization_service

    @get("/status")
    async def status(self) -> dict:
        # Cho admin biết SMTP đã cấu hình (điền username/password) hay chưa.
        user = require_login()
        await self._authz.require(user, "manage_system_settings")
        return {"enabled": self._email.enabled}

    @post("/test")
    async def send_test(self, body: EmailTestRequest) -> dict:
        # Gửi email thử (đồng bộ) -> báo kết quả ngay cho người test.
        user = require_login()
        await self._authz.require(user, "manage_system_settings")
        try:
            await self._email.send(
                EmailMessage(
                    to=[body.to],
                    subject=body.subject,
                    html=f"<p>{body.message}</p>",
                    text=body.message,
                )
            )
            return {"sent": True, "to": body.to}
        except MailError as exc:
            # Lỗi cấu hình/gửi -> trả thông điệp rõ thay vì 500
            return {"sent": False, "to": body.to, "error": str(exc)}
