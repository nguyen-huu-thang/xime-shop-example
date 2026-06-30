from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.entity.auth_token import AuthToken
from xime.starters.sqlalchemy import CrudRepository


class AuthTokenRepository(CrudRepository[AuthToken]):
    model = AuthToken

    async def find_active_by_hash(self, type_: str, token_hash: str) -> AuthToken | None:
        # Token còn hiệu lực theo hash (cho verify_email/reset_password - token định danh user)
        # Active token by hash (verify_email/reset_password - token identifies the user)
        result = await self.session.execute(
            select(AuthToken).where(
                AuthToken.type == type_,
                AuthToken.token_hash == token_hash,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > datetime.now(UTC),
            )
        )
        return result.scalar_one_or_none()

    async def find_active_for_user(self, user_id: int, type_: str) -> AuthToken | None:
        # OTP còn hiệu lực mới nhất của user (cho luồng OTP - cần ngữ cảnh user)
        # Latest active token for a user (OTP flow)
        result = await self.session.execute(
            select(AuthToken)
            .where(
                AuthToken.user_id == user_id,
                AuthToken.type == type_,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > datetime.now(UTC),
            )
            .order_by(AuthToken.id.desc())
        )
        return result.scalars().first()

    async def invalidate_unused_for_user(self, user_id: int, type_: str) -> None:
        # Vô hiệu hóa các token chưa dùng cùng loại của user (trước khi tạo cái mới)
        # Mark previous unused tokens of this type used (before issuing a new one)
        await self.session.execute(
            delete(AuthToken).where(
                AuthToken.user_id == user_id,
                AuthToken.type == type_,
                AuthToken.used_at.is_(None),
            )
        )

    async def delete_expired(self) -> None:
        await self.session.execute(
            delete(AuthToken).where(AuthToken.expires_at < datetime.now(UTC))
        )
