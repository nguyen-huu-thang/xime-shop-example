from __future__ import annotations

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.coupon_request import CouponCreateRequest, CouponUpdateRequest
from app.dto.response.coupon_response import CouponResponse
from app.dto.response.token_response import MessageResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.coupon_service import CouponService


class CouponController:
    prefix = "/api/coupons"
    tags = ["coupons"]

    def __init__(
        self,
        coupon_service: CouponService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = coupon_service
        self._authz = authorization_service

    @get("")
    async def list(self) -> list[CouponResponse]:
        user = require_login()
        await self._authz.require(user, "view_coupons")
        coupons = await self._svc.get_all_coupons()
        return [CouponResponse.model_validate(c) for c in coupons]

    @get("/{id}")
    async def detail(self, id: int) -> CouponResponse:
        user = require_login()
        await self._authz.require(user, "view_coupons")
        coupon = await self._svc.get_coupon_by_id(id)
        if not coupon:
            raise AppException("E10701")
        return CouponResponse.model_validate(coupon)

    @post("", status_code=201)
    async def create(self, body: CouponCreateRequest) -> CouponResponse:
        user = require_login()
        await self._authz.require(user, "create_coupon")
        data = body.model_dump(by_alias=False)
        coupon = await self._svc.create_coupon(data)
        return CouponResponse.model_validate(coupon)

    @put("/{id}")
    async def update(self, id: int, body: CouponUpdateRequest) -> CouponResponse:
        user = require_login()
        await self._authz.require(user, "edit_coupon")  # PHP typo "cedit_coupon" corrected
        data = body.model_dump(by_alias=False, exclude_unset=True)
        coupon = await self._svc.update_coupon(id, data)
        return CouponResponse.model_validate(coupon)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_coupon")
        await self._svc.delete_coupon(id)
        return MessageResponse(message="Coupon deleted")
