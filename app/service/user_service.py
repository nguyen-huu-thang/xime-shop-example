"""
UserService — quản lý user, port từ UserService.php (phần auth).

Các method khác (CRUD user, pagination) sẽ bổ sung ở Phase 4+.
"""
from __future__ import annotations

from passlib.context import CryptContext
from xime.core.transaction.manager import TransactionManager

from app.entity.user import User
from app.exception.app_exception import AppException
from app.repository.user_repository import UserRepository

_crypt = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    def __init__(
        self,
        transaction: TransactionManager,
        user_repository: UserRepository,
    ) -> None:
        self._transaction = transaction
        self._user_repo = user_repository

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Return user by id (active or not). None if not found."""
        async with self._transaction():
            return await self._user_repo.find(user_id)

    async def verify_user_password(self, username: str, password: str) -> User:
        """Return active user if credentials are valid.
        Trả về user đang hoạt động nếu thông tin đăng nhập hợp lệ.
        Raises E1004 nếu không tìm thấy, E1005 nếu sai mật khẩu.
        """
        async with self._transaction():
            user = await self._user_repo.find_by_username(username)
        if not user:
            raise AppException("E1004")
        if not _crypt.verify(password, user.password):
            raise AppException("E1005")
        return user

    async def verify_password(self, user: User, password: str) -> bool:
        """Verify password against stored hash (no DB call needed).
        Xác thực mật khẩu với hash đã lưu (không cần truy vấn DB).
        """
        return _crypt.verify(password, user.password)

    async def change_user_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        """Change user password after verifying the current one.
        Đổi mật khẩu sau khi xác thực mật khẩu hiện tại — E1024 nếu sai.
        """
        if not _crypt.verify(current_password, user.password):
            raise AppException("E1024")
        async with self._transaction():
            db_user = await self._user_repo.find(user.id)
            if not db_user:
                raise AppException("E1004")
            db_user.password = _crypt.hash(new_password)
            await self._user_repo.save(db_user)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plain-text password with bcrypt.
        Băm mật khẩu bằng bcrypt — dùng khi tạo user mới.
        """
        return _crypt.hash(password)
