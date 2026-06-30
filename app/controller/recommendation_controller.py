from __future__ import annotations

from xime.adapters.web.routing import get, post

from app.dto.response.token_response import MessageResponse
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.cooccurrence_service import CooccurrenceService
from app.service.recommendation_service import RecommendationService


class RecommendationController:
    prefix = "/api/recommendations"
    tags = ["recommendations"]

    def __init__(
        self,
        recommendation_service: RecommendationService,
        cooccurrence_service: CooccurrenceService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = recommendation_service
        self._cooccurrence = cooccurrence_service
        self._authz = authorization_service

    @get("/recently-viewed")
    async def recently_viewed(self, limit: int = 10) -> list[dict]:
        # Sản phẩm user xem gần đây (cá nhân, cần đăng nhập)
        # Products the user viewed recently (personal, login required)
        user = require_login()
        return await self._svc.recently_viewed(user.id, limit)

    @get("/trending")
    async def trending(self, limit: int = 10) -> list[dict]:
        # Thịnh hành toàn site (công khai)
        # Site-wide trending (public)
        return await self._svc.trending(limit)

    @get("/for-you")
    async def for_you(self, limit: int = 10) -> list[dict]:
        # Gợi ý cá nhân hóa theo affinity; cold-start -> trending (cần đăng nhập)
        # Personalized recommendations by affinity; cold-start -> trending (login required)
        user = require_login()
        return await self._svc.for_you(user.id, limit)

    @post("/admin/rebuild-cooccurrence")
    async def rebuild_cooccurrence(self) -> MessageResponse:
        # Dựng lại bảng "mua cùng" thủ công (Xime scheduler tự chạy định kỳ - xem config/scheduler.py).
        # Manual rebuild of the co-occurrence table (the Xime scheduler also runs it periodically).
        user = require_login()
        await self._authz.require(user, "manage_recommendations")
        written = await self._cooccurrence.rebuild()
        return MessageResponse(message=f"Co-occurrence rebuilt: {written} rows")
