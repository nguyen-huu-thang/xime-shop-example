from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ProfileUpdateRequest(BaseModel):
    # Self-service profile update (current user). At least one field required.
    # Cập nhật hồ sơ của chính mình. Cần ít nhất một trường.
    email: str | None = Field(default=None, min_length=3, max_length=255)
    phone: str | None = Field(default=None, max_length=15)
    address: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "ProfileUpdateRequest":
        if self.email is None and self.phone is None and self.address is None:
            raise ValueError("Cần ít nhất một trường để cập nhật")
        return self


class ActiveStatusRequest(BaseModel):
    # Activate/deactivate a user.
    # Kích hoạt/khóa user.
    is_active: bool = Field(alias="isActive")

    model_config = {"populate_by_name": True}


class RegisterRequest(BaseModel):
    # Public self-registration. Username/email uniqueness checked in the service.
    # Tự đăng ký công khai. Trùng username/email được kiểm tra ở service.
    username: str = Field(min_length=3, max_length=20)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=255)
    phone: str | None = Field(default=None, max_length=15)
    address: str | None = Field(default=None, max_length=255)


class UserCreateRequest(BaseModel):
    # Admin-created user (can set is_active).
    # User do admin tạo (có thể đặt is_active).
    username: str = Field(min_length=3, max_length=20)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=255)
    phone: str | None = Field(default=None, max_length=15)
    address: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True, alias="isActive")

    model_config = {"populate_by_name": True}


class UserUpdateRequest(BaseModel):
    # Admin update - every field optional; at least one required.
    # Admin cập nhật - mọi trường tùy chọn; cần ít nhất một.
    username: str | None = Field(default=None, min_length=3, max_length=20)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    password: str | None = Field(default=None, min_length=6, max_length=255)
    phone: str | None = Field(default=None, max_length=15)
    address: str | None = Field(default=None, max_length=255)
    is_active: bool | None = Field(default=None, alias="isActive")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UserUpdateRequest":
        if all(
            v is None
            for v in (
                self.username,
                self.email,
                self.password,
                self.phone,
                self.address,
                self.is_active,
            )
        ):
            raise ValueError("Cần ít nhất một trường để cập nhật")
        return self
