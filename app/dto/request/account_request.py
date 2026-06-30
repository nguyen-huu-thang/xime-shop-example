from __future__ import annotations

from pydantic import BaseModel, Field


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=255, alias="newPassword")

    model_config = {"populate_by_name": True}


class OtpVerifyRequest(BaseModel):
    otp: str = Field(min_length=4, max_length=10)
