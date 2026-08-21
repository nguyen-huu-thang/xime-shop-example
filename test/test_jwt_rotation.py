"""
Regression cho tầng JWT sau khi chuyển sang starter jwt của Xime (2026-08-21).

Bốn tính chất được canh, và mỗi cái tương ứng một cách hỏng có thật:

1. Token phát ra mang header `kid` -> có kid thì mới xoay được khóa; không có thì mọi lần đổi
   khóa là một lần đăng xuất toàn bộ người dùng.
2. Token ký bằng khóa CŨ vẫn verify được khi khóa đó còn trong jwt.previous_keys -> đó chính
   là cửa sổ gối đầu làm cho việc xoay khóa không cắt dịch vụ.
3. Token mang `kid` KHÔNG có trong danh sách -> từ chối (E1020), kể cả khi ký bằng secret đúng.
4. Token hết hạn -> E1021, KHÔNG lẫn với E1020. Client dựa vào mã này để biết nên gọi
   /refresh-token thay vì bắt người dùng đăng nhập lại. Xime gói lỗi PyJWT thành
   AuthenticationException nên chỗ phân loại nằm ở app - test này là lưới đỡ cho nó.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from xime.testing import TestApplication

from app.config.dependency import dependency
from app.exception.app_exception import AppException
from app.security.jwt_key_provider import ShopJwtKeyProvider
from app.service.authentication_service import AuthenticationService


def _claims(issuer: str, audience: str, **over) -> dict:
    now = datetime.now(UTC)
    base = {
        "jti": uuid.uuid4().hex,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "uid": 1,
        "username": "tester",
        "type": "access",
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_issued_token_carries_kid_header():
    async with TestApplication(binding=dependency) as app:
        auth = app.get(AuthenticationService)
        keys = app.get(ShopJwtKeyProvider)
        token = auth._signer.sign(
            _claims(auth._issuer, auth._audience), keys.signing_key
        )
        assert pyjwt.get_unverified_header(token)["kid"] == keys.signing_key.key_id


@pytest.mark.asyncio
async def test_token_signed_with_retired_key_still_verifies():
    """Khóa cũ còn trong previous_keys thì token của nó vẫn dùng được (cửa sổ xoay khóa)."""
    async with TestApplication(binding=dependency) as app:
        auth = app.get(AuthenticationService)
        keys = app.get(ShopJwtKeyProvider)

        from xime.starters.jwt import KeyContext

        retired = KeyContext(algorithm="HS256", secret="secret-cu-cua-lan-xoay-truoc-du-32-ky-tu", key_id="k0")
        keys._by_kid["k0"] = retired  # mô phỏng jwt.previous_keys có mục k0
        try:
            token = auth._signer.sign(_claims(auth._issuer, auth._audience), retired)
            claims = auth.validate_token(token)
            assert claims["username"] == "tester"
        finally:
            keys._by_kid.pop("k0", None)


@pytest.mark.asyncio
async def test_token_with_unknown_kid_is_rejected():
    """kid lạ -> E1020, ngay cả khi secret trùng khóa đang dùng: khóa đã loại bỏ là đã loại bỏ."""
    async with TestApplication(binding=dependency) as app:
        auth = app.get(AuthenticationService)
        keys = app.get(ShopJwtKeyProvider)

        from xime.starters.jwt import KeyContext

        ghost = KeyContext(
            algorithm=keys.signing_key.algorithm,
            secret=keys.signing_key.secret,
            key_id="kid-khong-ton-tai",
        )
        token = auth._signer.sign(_claims(auth._issuer, auth._audience), ghost)
        with pytest.raises(AppException) as exc:
            auth.validate_token(token)
        assert exc.value.error_key == "E1020"


@pytest.mark.asyncio
async def test_expired_token_keeps_its_own_error_code():
    """Hết hạn -> E1021, không phải E1020. leeway=30s nên phải lùi xa hơn thế."""
    async with TestApplication(binding=dependency) as app:
        auth = app.get(AuthenticationService)
        keys = app.get(ShopJwtKeyProvider)
        past = datetime.now(UTC) - timedelta(hours=1)
        token = auth._signer.sign(
            _claims(auth._issuer, auth._audience, iat=past, exp=past + timedelta(minutes=1)),
            keys.signing_key,
        )
        with pytest.raises(AppException) as exc:
            auth.validate_token(token)
        assert exc.value.error_key == "E1021"
