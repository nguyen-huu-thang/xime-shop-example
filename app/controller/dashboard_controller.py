"""
DashboardController - số liệu tổng hợp cho quản trị.

GET /api/dashboard/stats - yêu cầu quyền access_admin_dashboard.
"""
from __future__ import annotations

from xime.adapters.web.routing import get

from app.dto.response.dashboard_response import DashboardStats
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.dashboard_service import DashboardService


class DashboardController:
    prefix = "/api/dashboard"
    tags = ["dashboard"]

    def __init__(
        self,
        dashboard_service: DashboardService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = dashboard_service
        self._authz = authorization_service

    @get("/stats")
    async def stats(self) -> DashboardStats:
        user = require_login()
        await self._authz.require(user, "access_admin_dashboard")
        return await self._svc.get_stats()
