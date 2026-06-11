from __future__ import annotations

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.category_request import CategoryCreateRequest, CategoryUpdateRequest
from app.dto.response.category_response import CategoryResponse
from app.dto.response.token_response import MessageResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.category_service import CategoryService


class CategoryController:
    prefix = "/api/categories"
    tags = ["categories"]

    def __init__(
        self,
        category_service: CategoryService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = category_service
        self._authz = authorization_service

    async def _to_response(self, cat) -> CategoryResponse:
        """Build CategoryResponse with hierarchy paths.
        Build CategoryResponse kèm đường dẫn phân cấp.
        """
        path = await self._svc.build_hierarchy_path(cat)
        path_by_id = await self._svc.build_hierarchy_path_by_id(cat)
        return CategoryResponse(
            id=cat.id,
            name=cat.name,
            description=cat.description,
            parent_id=cat.parent_id,
            hierarchy_path=path,
            hierarchy_path_by_id=path_by_id,
        )

    @get("")
    async def list(self) -> list[CategoryResponse]:
        cats = await self._svc.get_all_categories()
        return [await self._to_response(c) for c in cats]

    @get("/{id}")
    async def detail(self, id: int) -> CategoryResponse:
        cat = await self._svc.get_category_by_id(id)
        if not cat:
            raise AppException("E10300")
        return await self._to_response(cat)

    @post("", status_code=201)
    async def create(self, body: CategoryCreateRequest) -> CategoryResponse:
        user = require_login()
        await self._authz.require(user, "create_category")
        data = body.model_dump(by_alias=False)
        cat = await self._svc.create_category(data)
        return await self._to_response(cat)

    @put("/{id}")
    async def update(self, id: int, body: CategoryUpdateRequest) -> CategoryResponse:
        user = require_login()
        await self._authz.require(user, "edit_category", target_id=id)
        data = body.model_dump(by_alias=False, exclude_unset=True)
        cat = await self._svc.update_category(id, data)
        return await self._to_response(cat)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_category")
        await self._svc.delete_category(id)
        return MessageResponse(message="Category deleted")

    @get("/{id}/subcategories")
    async def subcategories(self, id: int) -> list[CategoryResponse]:
        parent = await self._svc.get_category_by_id(id)
        if not parent:
            raise AppException("E10300")
        subs = await self._svc.get_subcategories_by_parent_id(id)
        return [await self._to_response(s) for s in subs]
