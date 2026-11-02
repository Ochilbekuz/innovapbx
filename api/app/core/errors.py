"""Yagona xato formati — m0-contract.md:
`{"error": {"code": "snake_case", "message": "...", "field": "...?", "details": {}}}`
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """Boshqariladigan xato — status, kod, xabar, ixtiyoriy field/details."""

    def __init__(self, status_code: int, code: str, message: str, *,
                 field: str | None = None, details: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(message)

    def body(self) -> dict:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.field is not None:
            err["field"] = self.field
        if self.details:
            err["details"] = self.details
        return {"error": err}


def _error_response(status_code: int, code: str, message: str, **extra: Any) -> JSONResponse:
    err = {"code": code, "message": message, **extra}
    return JSONResponse(status_code=status_code, content={"error": err})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.body())

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return _error_response(422, "validation_error", "So'rov ma'lumotlari yaroqsiz",
                                field=field or None)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Xato"
        return _error_response(exc.status_code, "http_error", detail)
