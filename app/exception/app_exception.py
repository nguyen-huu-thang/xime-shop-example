"""
AppException - port từ src/Exception/AppException.php.

    raise AppException("E2021")                         # message mặc định
    raise AppException("E10711", "Dữ liệu sai định dạng")  # override message
"""
from __future__ import annotations

from app.exception.error_code import get_error


class AppException(Exception):
    def __init__(self, error_key: str, custom_message: str | None = None) -> None:
        err = get_error(error_key)
        self.error_key = error_key
        self.code = err.code
        self.http_status = err.http_status
        self.message = custom_message or err.message
        super().__init__(self.message)
