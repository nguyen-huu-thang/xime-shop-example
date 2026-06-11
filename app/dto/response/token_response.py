from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Response cho /api/login — trả về cả access + refresh token."""
    accessToken: str
    refreshToken: str


class AccessTokenResponse(BaseModel):
    """Response cho /api/refresh-token — trả về access token mới."""
    accessToken: str


class RefreshTokenResponse(BaseModel):
    """Response cho /api/refresh-refresh-token — trả về refresh token mới."""
    refreshToken: str


class MessageResponse(BaseModel):
    """Response chung mang thông báo văn bản."""
    message: str
