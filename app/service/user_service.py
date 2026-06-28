"""
UserService - quản lý user, port từ UserService.php (phần auth).

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
        Đổi mật khẩu sau khi xác thực mật khẩu hiện tại - E1024 nếu sai.
        """
        if not _crypt.verify(current_password, user.password):
            raise AppException("E1024")
        async with self._transaction():
            db_user = await self._user_repo.find(user.id)
            if not db_user:
                raise AppException("E1004")
            db_user.password = _crypt.hash(new_password)
            await self._user_repo.save(db_user)

    async def get_users_paginated(self, page: int, limit: int) -> list[User]:
        async with self._transaction():
            return await self._user_repo.find_all_paginated(page, limit)

    async def count_users(self) -> int:
        async with self._transaction():
            return await self._user_repo.count()

    async def create_user(self, data: dict) -> User:
        """Create a new user (shared by /register and admin create).
        Tạo user mới (dùng chung cho /register và admin tạo).
        E1010/E1011/E1014 nếu thiếu trường; E1006/E1001 nếu trùng username/email.
        """
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        if not username:
            raise AppException("E1010")  # invalid/missing username
        if not email:
            raise AppException("E1011")  # invalid/missing email
        if not password:
            raise AppException("E1014")  # invalid/missing password

        async with self._transaction():
            if await self._user_repo.find_by_username(username):
                raise AppException("E1006")  # username đã tồn tại
            if await self._user_repo.find_by_email(email):
                raise AppException("E1001")  # email đã tồn tại

            user = User(
                username=username,
                email=email,
                password=_crypt.hash(password),
                phone=data.get("phone"),
                address=data.get("address"),
                is_active=data.get("is_active", True),
            )
            return await self._user_repo.save(user)

    async def update_user(self, user_id: int, data: dict) -> User:
        """Admin update of a user (username/email/password/phone/address/is_active).
        Admin cập nhật user. Kiểm tra trùng username/email -> E1006/E1001.
        """
        new_username = data.get("username")
        new_email = data.get("email")
        async with self._transaction():
            db_user = await self._user_repo.find(user_id)
            if not db_user:
                raise AppException("E1004")

            if new_username is not None and new_username != db_user.username:
                existing = await self._user_repo.find_by_username(new_username)
                if existing and existing.id != user_id:
                    raise AppException("E1006")
                db_user.username = new_username
            if new_email is not None and new_email != db_user.email:
                existing = await self._user_repo.find_by_email(new_email)
                if existing and existing.id != user_id:
                    raise AppException("E1001")
                db_user.email = new_email
            if data.get("password"):
                db_user.password = _crypt.hash(data["password"])
            if data.get("phone") is not None:
                db_user.phone = data["phone"]
            if data.get("address") is not None:
                db_user.address = data["address"]
            if data.get("is_active") is not None:
                db_user.is_active = data["is_active"]

            await self._user_repo.save(db_user)
            return db_user

    async def set_user_active(self, user_id: int, is_active: bool) -> User:
        """Activate/deactivate a user (soft enable/disable).
        Kích hoạt/khóa user.
        """
        async with self._transaction():
            db_user = await self._user_repo.find(user_id)
            if not db_user:
                raise AppException("E1004")
            db_user.is_active = is_active
            await self._user_repo.save(db_user)
            return db_user

    async def delete_user(self, user_id: int) -> None:
        """Hard delete a user. Protect the seeded admin accounts (E10101).
        Xóa cứng user. Bảo vệ tài khoản admin seed (E10101).
        """
        async with self._transaction():
            db_user = await self._user_repo.find(user_id)
            if not db_user:
                raise AppException("E1004")
            # Mirror PHP: never delete the bootstrap admin accounts.
            # Giống PHP: không bao giờ xóa tài khoản admin khởi tạo.
            if db_user.username in ("admin", "superadmin"):
                raise AppException("E10101")
            await self._user_repo.delete(db_user)

    async def update_profile(self, user_id: int, data: dict) -> User:
        """Update the current user's own profile (email/phone/address).
        Cập nhật hồ sơ của chính user (email/phone/address).
        Kiểm tra email trùng -> E1001.
        """
        new_email = data.get("email")
        async with self._transaction():
            db_user = await self._user_repo.find(user_id)
            if not db_user:
                raise AppException("E1004")

            if new_email is not None and new_email != db_user.email:
                existing = await self._user_repo.find_by_email(new_email)
                if existing and existing.id != user_id:
                    raise AppException("E1001")
                db_user.email = new_email
            if data.get("phone") is not None:
                db_user.phone = data["phone"]
            if data.get("address") is not None:
                db_user.address = data["address"]

            await self._user_repo.save(db_user)
            return db_user

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plain-text password with bcrypt.
        Băm mật khẩu bằng bcrypt - dùng khi tạo user mới.
        """
        return _crypt.hash(password)
