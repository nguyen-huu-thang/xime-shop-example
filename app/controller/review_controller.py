from __future__ import annotations

from xime.adapters.web.routing import delete, get, patch, post, put

from app.dto.request.review_request import ReviewCreateRequest, ReviewUpdateRequest
from app.dto.response.review_response import ReviewResponse
from app.dto.response.token_response import MessageResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
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

    @get("/{id}")
    async def detail(self, id: int) -> ReviewResponse:
        review = await self._svc.get_review_by_id(id)
        if not review:
            raise AppException("E10200")
        return ReviewResponse.model_validate(review)

    @post("", status_code=201)
    async def create(self, body: ReviewCreateRequest) -> ReviewResponse:
        require_login()
        data = body.model_dump(by_alias=True)
        review = await self._svc.create_review(data)
        return ReviewResponse.model_validate(review)

    @put("/{id}")
    async def update(self, id: int, body: ReviewUpdateRequest) -> ReviewResponse:
        require_login()
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
