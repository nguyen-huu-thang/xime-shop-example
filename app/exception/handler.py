"""
Exception handler - map AppException (và lỗi validation) → JSON response.

Framework Xime chưa có hook public để add exception handler, nên ta đăng ký
trực tiếp lên FastAPI app thông qua ShopWebAdapter.build_app() (xem
app/shop_web_adapter.py). Xem [.claude/framework-issues/issue-002].
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exception.app_exception import AppException


async def _app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    # Lỗi nghiệp vụ → JSON chuẩn {errorKey, code, message}
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "errorKey": exc.error_key,
            "code": exc.code,
            "message": exc.message,
        },
    )


async def _validation_exception_handler(
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


def register_exception_handlers(app: FastAPI) -> None:
    """Đăng ký toàn bộ exception handler lên FastAPI app."""
    app.add_exception_handler(AppException, _app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)  # type: ignore[arg-type]
