"""
Exception handler - map AppException (và lỗi validation) → JSON response.

Đăng ký qua configure_exception_handlers({...}) trong app/config/web.py
(API của framework Xime). Không cần subclass WebAdapter nữa.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exception.app_exception import AppException


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    # Lỗi nghiệp vụ → JSON chuẩn {errorKey, code, message}
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "errorKey": exc.error_key,
            "code": exc.code,
            "message": exc.message,
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Lỗi validate request (Pydantic) → đồng nhất về dạng E10711, kèm chi tiết
    return JSONResponse(
        status_code=400,
        content={
            "errorKey": "E10711",
            "code": 10711,
            "message": "Dữ liệu đầu vào không đúng định dạng",
            "details": exc.errors(),
        },
    )
