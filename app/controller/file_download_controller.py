"""
FileDownloadController - phục vụ file đã upload công khai tại /media/<key>.

Public (không cần đăng nhập): JwtMiddleware cho request không có header Authorization đi thẳng
qua, nên thẻ <img>/trình duyệt tải được. Stream object qua StorageService (helper stream_object
của framework) nên hỗ trợ HTTP Range/ETag và đổi backend (localfs <-> s3) không phải sửa controller.

Key chính là cột file_path trong bảng files, dạng "{2}/{2}/{rest}.ext" (chứa dấu '/'), nên route
dùng path converter {key:path}.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import StreamingResponse

from xime.adapters.web.files import stream_object
from xime.adapters.web.routing import get
from xime.starters.storage import StorageService

# Suy content-type từ đuôi tệp (LocalFileStorage.stat() không trả content_type).
# Infer content-type from extension (LocalFileStorage.stat() returns no content_type).
_CONTENT_TYPE_BY_EXT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "pdf": "application/pdf",
    "mp4": "video/mp4",
    "webm": "video/webm",
}


class FileDownloadController:
    prefix = "/media"
    tags = ["media"]

    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    @get("/{key:path}")
    async def download(self, key: str, request: Request) -> StreamingResponse:
        ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
        content_type = _CONTENT_TYPE_BY_EXT.get(ext)
        # stream_object: thiếu object -> 404; Range hợp lệ -> 206; ngược lại 200.
        # stream_object: missing object -> 404; valid Range -> 206; otherwise 200.
        return await stream_object(
            self._storage, key, request=request, content_type=content_type
        )
