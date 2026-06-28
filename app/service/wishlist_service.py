from xime.core.transaction.manager import TransactionManager

from app.entity.wishlist import Wishlist
from app.exception.app_exception import AppException
from app.repository.wishlist_repository import WishlistRepository
from app.service.product_service import ProductService
from app.service.user_service import UserService


class WishlistService:
    def __init__(
        self,
        transaction: TransactionManager,
        wishlist_repository: WishlistRepository,
        user_service: UserService,
        product_service: ProductService,
    ) -> None:
        self._transaction = transaction
        self._repo = wishlist_repository
        self._user_svc = user_service
        self._product_svc = product_service

    async def get_all_wishlist_items(self) -> list[Wishlist]:
        async with self._transaction():
            return await self._repo.find_all()

    async def get_wishlist_item_by_id(self, item_id: int) -> Wishlist | None:
        async with self._transaction():
            return await self._repo.find(item_id)

    async def get_wishlist_by_user(self, user_id: int) -> list[Wishlist]:
        async with self._transaction():
            return await self._repo.find_by_user_id(user_id)

    async def get_products_by_user(self, user_id: int) -> list:
        # Returns list of product_ids from user's wishlist
        # Trả về danh sách product_id từ wishlist của user
        async with self._transaction():
            items = await self._repo.find_by_user_id(user_id)
        products = []
        for item in items:
            product = await self._product_svc.get_product_by_id(item.product_id)
            if product:
                products.append(product)
        return products

    async def get_user_wishlist_detail(self, user_id: int) -> list[dict]:
        # Return wishlist lines WITH their wishlist id so the client can delete them
        # (DELETE /api/wishlist/{id} needs the wishlist item id, not the product id).
        # Trả về các dòng wishlist KÈM id wishlist để client có thể xóa
        # (DELETE /api/wishlist/{id} cần id của wishlist item, không phải product id).
        async with self._transaction():
            items = await self._repo.find_by_user_id(user_id)
        result: list[dict] = []
        for item in items:
            product = await self._product_svc.get_product_by_id(item.product_id)
            if product:
                result.append(
                    {
                        "wishlistId": item.id,
                        "productId": product.id,
                        "name": product.name,
                    }
                )
        return result

    async def create_wishlist_item(self, data: dict, user_id: int) -> Wishlist:
        product = await self._product_svc.get_product_by_id(data["productId"])
        if not product:
            raise AppException("E10200")

        async with self._transaction():
            item = Wishlist(user_id=user_id, product_id=product.id)
            return await self._repo.save(item)

    async def delete_wishlist_item(self, item_id: int, user_id: int) -> None:
        async with self._transaction():
            item = await self._repo.find(item_id)
            if not item:
                raise AppException("E10200")
            if item.user_id != user_id:
                raise AppException("E2021")
            await self._repo.delete(item)
