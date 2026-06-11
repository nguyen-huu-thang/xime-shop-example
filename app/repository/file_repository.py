from sqlalchemy import select

from app.entity.file import File
from app.repository.base_repository import BaseRepository


class FileRepository(BaseRepository[File]):
    model = File

    async def find_by_user(self, user_id: int) -> list[File]:
        result = await self.session.execute(
            select(File).where(File.user_id == user_id)
        )
        return list(result.scalars().all())

    async def find_by_target(
        self, table_name: str, target_id: int, only_active: bool = True
    ) -> list[File]:
        # Find files associated with a specific table+record (polymorphic)
        # Tìm file gắn với bảng+bản ghi cụ thể (quan hệ đa hình)
        stmt = select(File).where(
            File.list_table_id == table_name,
            File.target_id == target_id,
        )
        if only_active:
            stmt = stmt.where(File.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_all_paginated(self, page: int, limit: int) -> list[File]:
        offset = (page - 1) * limit
        result = await self.session.execute(
            select(File).order_by(File.id.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def find_inactive(self) -> list[File]:
        result = await self.session.execute(
            select(File).where(File.is_active == False)  # noqa: E712
        )
        return list(result.scalars().all())
