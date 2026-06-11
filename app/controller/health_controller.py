from __future__ import annotations

from xime.adapters.web import get


class HealthController:
    """Health-check endpoint — xác minh app + routing hoạt động."""

    prefix = "/api"
    tags = ["health"]

    @get("/health")
    async def health(self) -> dict:
        # Simple liveness probe
        # Kiểm tra sống đơn giản
        return {"status": "ok"}
