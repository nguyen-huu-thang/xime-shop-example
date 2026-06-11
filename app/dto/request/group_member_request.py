from __future__ import annotations

from pydantic import BaseModel, Field


class GroupMemberAddRequest(BaseModel):
    user_id: int = Field(gt=0)
    group_id: int = Field(gt=0)


class GroupMemberRemoveRequest(BaseModel):
    user_id: int = Field(gt=0)
    group_id: int = Field(gt=0)


class GroupMemberCheckRequest(BaseModel):
    user_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
