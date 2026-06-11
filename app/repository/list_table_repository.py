from app.entity.list_table import ListTable
from app.repository.base_repository import BaseRepository


class ListTableRepository(BaseRepository[ListTable]):
    model = ListTable

    async def find_by_table_name(self, table_name: str) -> ListTable | None:
        # PK of list_table is the table name string itself
        # PK của list_table chính là tên bảng (string)
        return await self.session.get(ListTable, table_name)
