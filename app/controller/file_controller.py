from __future__ import annotations

import os

from fastapi import Form, UploadFile

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.file_request import FileUpdateRequest
from app.dto.response.file_response import FileResponse
from app.dto.response.token_response import CountResponse, MessageResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.file_service import FileService


class FileController:
    prefix = "/api/files"
    tags = ["files"]

    def __init__(
        self,
        file_service: FileService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = file_service
        self._authz = authorization_service

    @get("/all")
    async def list_all(self) -> list[FileResponse]:
        user = require_login()
        await self._authz.require(user, "view_files")
        files = await self._svc.get_all_files()
        return [FileResponse.model_validate(f) for f in files]

    @get("")
    async def list_paginated(self, page: int = 1, limit: int = 10) -> list[FileResponse]:
        user = require_login()
        await self._authz.require(user, "view_files")
        files = await self._svc.get_files_paginated(page, limit)
        return [FileResponse.model_validate(f) for f in files]

    @get("/count")
    async def count(self) -> CountResponse:
        # Total files for FE pagination (needs view_files).
        # Tổng số tệp cho phân trang FE (cần quyền view_files).
        user = require_login()
        await self._authz.require(user, "view_files")
        return CountResponse(total=await self._svc.count_files())

    @get("/inactive")
    async def list_inactive(self) -> list[FileResponse]:
        user = require_login()
        await self._authz.require(user, "view_files")
        files = await self._svc.get_inactive_files()
        return [FileResponse.model_validate(f) for f in files]

    @get("/user/{user_id}")
    async def by_user(self, user_id: int) -> list[FileResponse]:
        user = require_login()
        await self._authz.require(user, "view_files")
        files = await self._svc.get_files_by_user(user_id)
        return [FileResponse.model_validate(f) for f in files]

    @get("/product/{product_id}")
    async def by_product(self, product_id: int, only_active: bool = True) -> list[FileResponse]:
        files = await self._svc.get_files_by_product(product_id, only_active)
        return [FileResponse.model_validate(f) for f in files]

    @get("/review/{review_id}")
    async def by_review(self, review_id: int, only_active: bool = True) -> list[FileResponse]:
        files = await self._svc.get_files_by_review(review_id, only_active)
        return [FileResponse.model_validate(f) for f in files]

    @get("/{id}")
    async def detail(self, id: int) -> FileResponse:
        f = await self._svc.get_file_by_id(id)
        if not f:
            raise AppException("E10200")
        return FileResponse.model_validate(f)

    @post("", status_code=201)
    async def upload(
        self,
        file: UploadFile,
        description: str | None = Form(default=None),
        sort: int | None = Form(default=None),
        is_active: bool = Form(default=True),
        product_id: int | None = Form(default=None, alias="productId"),
        review_id: int | None = Form(default=None, alias="reviewId"),
    ) -> dict:
        # Multipart upload: delegate streaming to the service (no full RAM buffer)
        # Upload multipart: service stream thẳng vào storage, không nạp hết vào RAM
        user = require_login()

        if not file or not file.filename:
            raise AppException("E5001")

        original_name = file.filename
        _, ext = os.path.splitext(original_name)
        extension = ext.lstrip(".").lower()

        data = {
            "description": description,
            "sort": sort,
            "isActive": is_active,
        }
        if product_id is not None:
            data["productId"] = product_id
        if review_id is not None:
            data["reviewId"] = review_id

        db_file = await self._svc.upload_file(
            upload_file=file,
            original_name=original_name,
            extension=extension,
            user_id=user.id,
            data=data,
        )
        return {
            "message": "File uploaded successfully!",
            "id": db_file.id,
            "file": db_file.file_path,
        }

    @put("/{id}")
    async def update(self, id: int, body: FileUpdateRequest) -> FileResponse:
        require_login()
        data = body.model_dump(exclude_unset=True, by_alias=True)
        db_file = await self._svc.update_info_file(id, data)
        return FileResponse.model_validate(db_file)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_file")
        await self._svc.delete_file(id)
        return MessageResponse(message="File deleted successfully!")
