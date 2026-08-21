import logging
import secrets
from datetime import datetime, timezone

from fastapi import UploadFile

from xime.adapters.web.files import PayloadTooLarge, save_upload
from xime.core.transaction.manager import TransactionManager
from xime.starters.storage import StorageError, StorageService

from app.entity.file import File
from app.exception.app_exception import AppException
from app.repository.file_repository import FileRepository
from app.service.list_table_service import ListTableService
from app.service.user_service import UserService

logger = logging.getLogger(__name__)

# Giới hạn dung lượng mỗi file upload (10 MB).
# Per-file upload size cap (10 MB).
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class FileService:
    def __init__(
        self,
        transaction: TransactionManager,
        storage: StorageService,
        file_repository: FileRepository,
        user_service: UserService,
        list_table_service: ListTableService,
    ) -> None:
        self._transaction = transaction
        self._storage = storage
        self._repo = file_repository
        self._user_svc = user_service
        self._list_table_svc = list_table_service

    def _generate_random_name(self, length: int = 32) -> str:
        # 32 hex chars from 16 random bytes - mirrors PHP bin2hex(random_bytes(16))
        # 32 ký tự hex từ 16 byte ngẫu nhiên - giống PHP bin2hex(random_bytes(16))
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

    async def count_files(self) -> int:
        # Total files (for FE pagination).
        # Tổng số tệp (phục vụ phân trang FE).
        async with self._transaction():
            return await self._repo.count()

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
        upload_file: UploadFile,
        original_name: str,
        extension: str,
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

        # Stream thẳng vào storage theo chunk (không nạp hết vào RAM), giới hạn dung lượng.
        # Stream straight into storage chunk by chunk with a size cap (never buffer in RAM).
        #
        # KHÔNG truyền content_type: Xime 0.7.1 (bản vá F2) cố ý suy content type từ TÊN FILE
        # chứ không lấy header Content-Type của phần multipart, vì header đó do kẻ gọi điều
        # khiển và backend S3 trả lại y nguyên lúc tải về - đó là đường biến một "avatar.png"
        # khai text/html thành XSS lưu trữ. Trước đây chỗ này truyền lại đúng giá trị của
        # client nên bản vá của framework không có tác dụng.
        # Never forward the client's Content-Type: the framework derives it from the file name.
        try:
            file_size = await save_upload(
                self._storage,
                relative_path,
                upload_file,
                max_bytes=_MAX_UPLOAD_BYTES,
            )
        except PayloadTooLarge as exc:
            raise AppException("E5012") from exc  # vượt dung lượng cho phép (413)
        except StorageError as exc:
            logger.error("File upload error: %s", exc)
            raise AppException("E5010") from exc  # không thể tải tệp lên

        if file_size == 0:
            # Tệp rỗng: dọn object vừa tạo rồi báo lỗi.
            # Empty file: clean up the just-created object then fail.
            await self._storage.delete(relative_path)
            raise AppException("E5013")  # thiếu dữ liệu/tệp để tải lên

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
            # Giữ key trước khi đóng session (tránh expire_on_commit lazy-load).
            # Capture the storage key before the session closes.
            storage_key = db_file.file_path
            await self._repo.delete(db_file)

        # Xóa object vật lý sau khi commit DB (idempotent, no-op nếu đã mất).
        # Delete the physical object after the DB commit (idempotent, no-op if gone).
        await self._storage.delete(storage_key)
