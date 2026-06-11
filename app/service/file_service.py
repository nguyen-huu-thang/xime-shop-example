import logging
import os
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path

from xime.core.transaction.manager import TransactionManager

from app.entity.file import File
from app.exception.app_exception import AppException
from app.repository.file_repository import FileRepository
from app.service.list_table_service import ListTableService
from app.service.user_service import UserService

logger = logging.getLogger(__name__)

# Upload directory from environment variable, fallback to public/data
# Thư mục upload lấy từ biến môi trường, mặc định là public/data
_UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "public/data")


class FileService:
    def __init__(
        self,
        transaction: TransactionManager,
        file_repository: FileRepository,
        user_service: UserService,
        list_table_service: ListTableService,
    ) -> None:
        self._transaction = transaction
        self._repo = file_repository
        self._user_svc = user_service
        self._list_table_svc = list_table_service

    def _generate_random_name(self, length: int = 32) -> str:
        # 32 hex chars from 16 random bytes — mirrors PHP bin2hex(random_bytes(16))
        # 32 ký tự hex từ 16 byte ngẫu nhiên — giống PHP bin2hex(random_bytes(16))
        return secrets.token_hex(length // 2)

    def _build_file_path(self, random_name: str, extension: str) -> tuple[str, str, str]:
        # path = {2chars}/{2chars}/{rest}.ext
        # Cấu trúc: 2 ký tự đầu / 2 ký tự tiếp / phần còn lại.ext
        folder1 = random_name[:2]
        folder2 = random_name[2:4]
        filename = random_name[4:] + ("." + extension if extension else "")
        relative_path = f"{folder1}/{folder2}/{filename}"
        return folder1, folder2, relative_path

    async def get_all_files(self) -> list[File]:
        async with self._transaction():
            return await self._repo.find_all()

    async def get_files_paginated(self, page: int, limit: int) -> list[File]:
        async with self._transaction():
            return await self._repo.find_all_paginated(page, limit)

    async def get_file_by_id(self, file_id: int) -> File | None:
        async with self._transaction():
            return await self._repo.find(file_id)

    async def get_files_by_user(self, user_id: int) -> list[File]:
        async with self._transaction():
            return await self._repo.find_by_user(user_id)

    async def get_files_by_product(self, product_id: int, only_active: bool = True) -> list[File]:
        table = await self._list_table_svc.get_by_table_name("products")
        async with self._transaction():
            return await self._repo.find_by_target(table.id, product_id, only_active)

    async def get_files_by_review(self, review_id: int, only_active: bool = True) -> list[File]:
        table = await self._list_table_svc.get_by_table_name("reviews")
        async with self._transaction():
            return await self._repo.find_by_target(table.id, review_id, only_active)

    async def get_inactive_files(self) -> list[File]:
        async with self._transaction():
            return await self._repo.find_inactive()

    async def upload_file(
        self,
        file_content: bytes,
        original_name: str,
        extension: str,
        file_size: int,
        user_id: int,
        data: dict,
    ) -> File:
        # Validate user exists (separate read transaction)
        # Kiểm tra user tồn tại (transaction đọc riêng)
        user = await self._user_svc.get_user_by_id(user_id)
        if not user:
            raise AppException("E1004")

        # Resolve list_table entries outside write transaction to avoid nesting
        # Tra cứu list_table trước khi mở transaction ghi để tránh lồng transaction
        list_table_id: str | None = None
        target_id: int | None = None

        product_id = data.get("productId")
        if product_id and str(product_id).isnumeric():
            table = await self._list_table_svc.get_by_table_name("products")
            list_table_id = table.id
            target_id = int(product_id)

        review_id = data.get("reviewId")
        if review_id and str(review_id).isnumeric():
            table = await self._list_table_svc.get_by_table_name("reviews")
            list_table_id = table.id
            target_id = int(review_id)

        random_name = self._generate_random_name()
        _, _, relative_path = self._build_file_path(random_name, extension)

        full_path = Path(_UPLOAD_DIR) / relative_path
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(file_content)
        except Exception as exc:
            logger.error("File upload error: %s", exc)
            raise AppException("E5010") from exc

        # Build entity and persist
        # Tạo entity và lưu vào DB
        async with self._transaction():
            db_file = File(
                user_id=user_id,
                file_name=original_name,
                file_path=relative_path,
                file_size=file_size,
                uploaded_at=datetime.now(timezone.utc),
                is_active=data.get("isActive", True),
                description=data.get("description"),
                sort=data.get("sort"),
                list_table_id=list_table_id,
                target_id=target_id,
            )
            return await self._repo.save(db_file)

    async def update_info_file(self, file_id: int, data: dict) -> File:
        # Resolve list_table entries outside write transaction
        # Tra cứu list_table trước khi mở transaction ghi
        new_list_table_id: str | None = None
        new_target_id: int | None = None
        clear_target = False

        product_id = data.get("productId")
        if product_id and str(product_id).isnumeric():
            table = await self._list_table_svc.get_by_table_name("products")
            new_list_table_id = table.id
            new_target_id = int(product_id)
        elif "productId" in data and not product_id:
            clear_target = True

        review_id = data.get("reviewId")
        if review_id and str(review_id).isnumeric():
            table = await self._list_table_svc.get_by_table_name("reviews")
            new_list_table_id = table.id
            new_target_id = int(review_id)
        elif "reviewId" in data and not review_id:
            clear_target = True

        async with self._transaction():
            db_file = await self._repo.find(file_id)
            if not db_file:
                raise AppException("E10200")

            if "isActive" in data:
                db_file.is_active = data["isActive"]
            if "description" in data:
                db_file.description = data["description"]
            if "sort" in data:
                db_file.sort = data["sort"]

            if new_list_table_id is not None:
                db_file.list_table_id = new_list_table_id
                db_file.target_id = new_target_id
            elif clear_target:
                db_file.target_id = None

            return await self._repo.save(db_file)

    async def delete_file(self, file_id: int) -> None:
        async with self._transaction():
            db_file = await self._repo.find(file_id)
            if not db_file:
                raise AppException("E10200")

            # Remove physical file if it exists
            # Xóa file vật lý nếu tồn tại
            full_path = Path(_UPLOAD_DIR) / db_file.file_path
            if full_path.exists():
                try:
                    full_path.unlink()
                except Exception as exc:
                    logger.warning("Could not delete file %s: %s", full_path, exc)

            await self._repo.delete(db_file)
