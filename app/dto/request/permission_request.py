"""
Request DTOs cho assign/update/delete permission (user và group).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PermissionEntryRequest(BaseModel):
    """Một entry quyền: is_active, is_denied, target ('all' hoặc id số)."""
    is_active: bool = True
    is_denied: bool = False
    target: Any = "all"  # "all" or int target id


class AssignUserPermissionRequest(BaseModel):
    user_id: int = Field(gt=0)
    permissions: dict[str, PermissionEntryRequest]


class UpdateUserPermissionRequest(BaseModel):
    user_id: int = Field(gt=0)
    permissions: dict[str, PermissionEntryRequest]


class DeleteUserPermissionRequest(BaseModel):
    user_id: int = Field(gt=0)
    permissions: list[str]


class AssignGroupPermissionRequest(BaseModel):
    group_id: int = Field(gt=0)
    permissions: dict[str, PermissionEntryRequest]


class UpdateGroupPermissionRequest(BaseModel):
    group_id: int = Field(gt=0)
    permissions: dict[str, PermissionEntryRequest]


class DeleteGroupPermissionRequest(BaseModel):
    group_id: int = Field(gt=0)
    permissions: list[str]


class CheckPermissionRequest(BaseModel):
    """Request cho endpoint kiểm tra quyền trực tiếp."""
    permission_name: str
    target_id: int | None = None
