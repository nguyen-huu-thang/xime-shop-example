from xime.core.transaction.manager import TransactionManager

from app.entity.list_table import ListTable
from app.exception.app_exception import AppException
from app.repository.list_table_repository import ListTableRepository

# Static list of all table names - mirrors PHP ListTableService::syncListTable
# Danh sách tên bảng tĩnh - giống PHP ListTableService::syncListTable
_TABLE_DESCRIPTIONS: dict[str, str] = {
    "users": "Chứa thông tin của người dùng, bao gồm tài khoản, mật khẩu và các thông tin liên hệ.",
    "permissions": "Lưu giữ các quyền hạn của người dùng.",
    "groups": "Quản lý danh sách các nhóm người dùng.",
    "group_members": "Liên kết người dùng với nhóm.",
    "user_permissions": "Phân quyền chi tiết cho từng người dùng.",
    "group_permissions": "Phân quyền cho nhóm.",
    "categories": "Chứa danh mục sản phẩm, hỗ trợ phân loại.",
    "products": "Quản lý thông tin sản phẩm.",
    "product_attributes": "Xác định các thuộc tính của sản phẩm.",
    "product_attribute_values": "Lưu giá trị cho các thuộc tính.",
    "product_options": "Lưu các tùy chọn sản phẩm (giá + tồn kho).",
    "product_option_values": "Kết nối giá trị thuộc tính với tùy chọn sản phẩm.",
    "cart": "Lưu thông tin giỏ hàng của người dùng.",
    "wishlist": "Lưu các sản phẩm mà người dùng yêu thích.",
    "coupons": "Lưu mã giảm giá.",
    "orders": "Lưu thông tin đơn hàng.",
    "order_details": "Chi tiết từng sản phẩm trong đơn hàng.",
    "reviews": "Lưu đánh giá sản phẩm của người dùng.",
    "notifications": "Quản lý thông báo gửi cho người dùng.",
    "refresh_tokens": "Quản lý các token xác thực.",
    "blacklist_tokens": "Ngăn chặn token bị lạm dụng.",
    "files": "Lưu trữ thông tin tệp người dùng tải lên.",
    "interactions": "Theo dõi hành động của người dùng trên sản phẩm.",
    "actions": "Lưu danh sách các loại hành động người dùng.",
}


class ListTableService:
    def __init__(
        self,
        transaction: TransactionManager,
        list_table_repository: ListTableRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = list_table_repository

    async def get_by_table_name(self, table_name: str) -> ListTable:
        # Lookup list_table entry by its string PK (= table name)
        # Tra cứu bản ghi list_table theo PK là tên bảng
        async with self._transaction():
            table = await self._repo.find_by_table_name(table_name)
        if not table:
            raise AppException("E10200")
        return table

    async def get_all(self) -> list[ListTable]:
        async with self._transaction():
            return await self._repo.find_all()

    async def create_or_update(self, table_name: str, description: str | None) -> ListTable:
        async with self._transaction():
            existing = await self._repo.find_by_table_name(table_name)
            if existing is None:
                existing = ListTable(id=table_name, description=description)
            else:
                existing.description = description
            return await self._repo.save(existing)

    async def delete(self, table_name: str) -> None:
        async with self._transaction():
            item = await self._repo.find_by_table_name(table_name)
            if item:
                await self._repo.delete(item)

    async def sync_list_table(self) -> dict:
        # Sync static table list to DB - idempotent
        # Đồng bộ danh sách bảng tĩnh vào DB - có thể chạy nhiều lần
        async with self._transaction():
            existing = await self._repo.find_all()
        existing_ids = {t.id for t in existing}

        added = 0
        for table_name, desc in _TABLE_DESCRIPTIONS.items():
            if table_name not in existing_ids:
                await self.create_or_update(table_name, desc)
                added += 1

        return {"added": added, "total": len(_TABLE_DESCRIPTIONS)}
