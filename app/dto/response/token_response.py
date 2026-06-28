from pydantic import BaseModel


class AccessTokenResponse(BaseModel):
    """Response cho /api/login và /api/refresh-token.

    Chỉ trả access token trong body (client lưu RAM). Refresh token KHÔNG nằm trong
    body - nó được đặt vào httpOnly cookie path-scoped (xem app/security/cookies.py).
    """
    accessToken: str


class MessageResponse(BaseModel):
    """Response chung mang thông báo văn bản."""
    message: str


class CountResponse(BaseModel):
    """Response chung cho các endpoint đếm tổng bản ghi (phục vụ phân trang FE)."""
    total: int
