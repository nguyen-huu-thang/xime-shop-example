from __future__ import annotations

from xime.adapters.web.routing import delete, get, post

from app.dto.request.wishlist_request import WishlistCreateRequest
from app.dto.response.token_response import MessageResponse
from app.dto.response.wishlist_response import WishlistResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.interaction_service import InteractionService
from app.service.wishlist_service import WishlistService


class WishlistController:
    prefix = "/api/wishlist"
    tags = ["wishlist"]

    def __init__(
        self,
        wishlist_service: WishlistService,
        authorization_service: AuthorizationService,
        interaction_service: InteractionService,
    ) -> None:
        self._svc = wishlist_service
        self._authz = authorization_service
        self._interaction = interaction_service

    @get("/all")
    async def list(self) -> list[WishlistResponse]:
        user = require_login()
        await self._authz.require(user, "view_wishlists")
        items = await self._svc.get_all_wishlist_items()
        return [WishlistResponse.model_validate(i) for i in items]

    @get("")
    async def user_wishlist(self) -> list[dict]:
        # Returns the current user's wishlist lines, each with its wishlistId + productId
        # so the client can render and delete entries.
        # Trả về các dòng wishlist của user hiện tại, mỗi dòng kèm wishlistId + productId
        # để client hiển thị và xóa được.
        user = require_login()
        return await self._svc.get_user_wishlist_detail(user.id)

    @get("/{id}")
    async def detail(self, id: int) -> WishlistResponse:
        user = require_login()
        item = await self._svc.get_wishlist_item_by_id(id)
        if not item:
            raise AppException("E10200")
        # Vá IDOR: chủ sở hữu hoặc người có quyền view_wishlists mới được xem
        # Fix IDOR: only the owner or a holder of view_wishlists may view
        await self._authz.require_owner_or_permission(
            user, "view_wishlists", item, target_id=id
        )
        return WishlistResponse.model_validate(item)

    @post("", status_code=201)
    async def create(self, body: WishlistCreateRequest) -> WishlistResponse:
        user = require_login()
        data = body.model_dump(by_alias=True)
        item = await self._svc.create_wishlist_item(data, user.id)
        # Ghi tín hiệu "wishlist" cho cá nhân hóa (fault-tolerant)
        # Record a "wishlist" signal for personalization
        await self._interaction.record(user.id, item.product_id, "wishlist")
        return WishlistResponse.model_validate(item)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._svc.delete_wishlist_item(id, user.id)
        return MessageResponse(message="Wishlist item deleted")
