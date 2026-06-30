"""
Unit test cho EmailService (không cần DB, không cần SMTP thật).

Kiểm tra hành vi BẬT/TẮT theo cấu hình: khi chưa điền username/password thì email tự tắt
(send_safe trả False, send raise MailError) -> không gọi mạng khi chạy test/dev.
"""
import pytest

from app.service.email_service import EmailService
from xime.starters.mail import EmailMessage, MailError


class _FakeConfig:
    def __init__(self, data: dict) -> None:
        self._d = data

    def get(self, key, default=None):
        return self._d.get(key, default)


class _FakeMail:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


def _msg() -> EmailMessage:
    return EmailMessage(to=["a@b.com"], subject="s", text="t")


def test_email_disabled_when_no_credentials():
    svc = EmailService(_FakeMail(), _FakeConfig({}))
    assert svc.enabled is False


def test_email_enabled_with_credentials():
    cfg = _FakeConfig({"mail.smtp.username": "u@x.com", "mail.smtp.password": "pw"})
    svc = EmailService(_FakeMail(), cfg)
    assert svc.enabled is True


@pytest.mark.asyncio
async def test_send_safe_skips_when_disabled():
    mail = _FakeMail()
    svc = EmailService(mail, _FakeConfig({}))
    ok = await svc.send_safe(_msg())
    assert ok is False
    assert mail.sent == []  # không gọi backend khi tắt


@pytest.mark.asyncio
async def test_send_raises_when_disabled():
    svc = EmailService(_FakeMail(), _FakeConfig({}))
    with pytest.raises(MailError):
        await svc.send(_msg())


@pytest.mark.asyncio
async def test_send_safe_delivers_when_enabled():
    mail = _FakeMail()
    cfg = _FakeConfig({"mail.smtp.username": "u@x.com", "mail.smtp.password": "pw"})
    svc = EmailService(mail, cfg)
    ok = await svc.send_safe(_msg())
    assert ok is True
    assert len(mail.sent) == 1
