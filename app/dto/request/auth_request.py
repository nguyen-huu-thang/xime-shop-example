from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=1)
    # Nút tích "Đăng xuất tất cả phiên khác" - giữ phiên hiện tại, thu hồi refresh token phiên khác.
    # "Log out all other sessions" checkbox - keep current session, revoke other refresh tokens.
    logoutOtherSessions: bool = Field(default=False)


class VerifyPasswordRequest(BaseModel):
    password: str = Field(min_length=1)
