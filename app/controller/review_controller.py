from __future__ import annotations

from xime.adapters.web.routing import delete, get, patch, post, put

from app.dto.request.review_request import ReviewCreateRequest, ReviewUpdateRequest
from app.dto.response.review_response import ReviewResponse
from app.dto.response.token_response import MessageResponse
from app.exception.app_exception import AppException
from app.security.current_user import current_user, require_login
from app.service.authorization_service import AuthorizationService
from app.service.review_service import ReviewService


class ReviewController:
    prefix = "/api/reviews"
    tags = ["reviews"]

    def __init__(
        self,
        review_service: ReviewService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = review_service
        self._authz = authorization_service

    @get("")
    async def list(self) -> list[ReviewResponse]:
        user = require_login()
        await self._authz.require(user, "view_reviews")
        reviews = await self._svc.get_all_reviews()
        return [ReviewResponse.model_validate(r) for r in reviews]

    @get("/product/{product_id}")
    async def by_product(
        self, product_id: int, page: int = 1, limit: int = 10
    ) -> list[ReviewResponse]:
        # Public: approved reviews of a product for the detail page (no login)
        # Công khai: review đã duyệt của sản phẩm cho trang chi tiết (không cần đăng nhập)
        reviews = await self._svc.get_approved_reviews_by_product(product_id, page, limit)
        return [ReviewResponse.model_validate(r) for r in reviews]

    @get("/{id}")
    async def detail(self, id: int) -> ReviewResponse:
        review = await self._svc.get_review_by_id(id)
        if not review:
            raise AppException("E10600")
        # Review chưa duyệt chỉ chủ sở hữu hoặc người có quyền view_reviews mới xem được
        # (tránh lộ review chưa duyệt cho khách)
        if not review.is_approved:
            user = current_user()
            await self._authz.require_owner_or_permission(
                user, "view_reviews", review, target_id=id
            )
        return ReviewResponse.model_validate(review)

    @post("", status_code=201)
    async def create(self, body: ReviewCreateRequest) -> ReviewResponse:
        user = require_login()
        data = body.model_dump(by_alias=True)
        # Gán userId theo user đăng nhập (không tin userId từ client)
        data["userId"] = user.id
        review = await self._svc.create_review(data)
        return ReviewResponse.model_validate(review)

    @put("/{id}")
    async def update(self, id: int, body: ReviewUpdateRequest) -> ReviewResponse:
        # Chỉ chủ sở hữu review (hoặc người có quyền delete_review = admin) mới sửa được (vá IDOR)
        user = require_login()
        review = await self._svc.get_review_by_id(id)
        if not review:
            raise AppException("E10600")
        await self._authz.require_owner_or_permission(
            user, "delete_review", review, target_id=id
        )
        data = body.model_dump(exclude_unset=True)
        review = await self._svc.update_review(id, data)
        return ReviewResponse.model_validate(review)

    @patch("/{id}/approve")
    async def approve(self, id: int) -> ReviewResponse:
        user = require_login()
        await self._authz.require(user, "approve_disapprove_review")
        review = await self._svc.approve_review(id)
        return ReviewResponse.model_validate(review)

    @patch("/{id}/disapprove")
    async def disapprove(self, id: int) -> ReviewResponse:
        user = require_login()
        await self._authz.require(user, "approve_disapprove_review")
        review = await self._svc.disapprove_review(id)
        return ReviewResponse.model_validate(review)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_review")
        await self._svc.delete_review(id)
        return MessageResponse(message="Review deleted")
