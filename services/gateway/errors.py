"""Conversão de exceções em respostas de erro padronizadas: {"error": {code, message, retryable, details}}."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from squadforce_shared.errors import AppError, ErrorCode

log = logging.getLogger("squadforce.gateway")


def _body(code: ErrorCode | str, message: str, retryable: bool = False, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code.value if isinstance(code, ErrorCode) else code,
            "message": message,
            "retryable": retryable,
            "details": details or {},
        }
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_body())

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_body(ErrorCode.VALIDATION_ERROR, "Dados de entrada inválidos.", details={"errors": jsonable_encoder(errors)}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.VALIDATION_ERROR
        msg = "Recurso não encontrado." if exc.status_code == 404 else str(exc.detail)
        return JSONResponse(status_code=exc.status_code, content=_body(code, msg))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_body(ErrorCode.INTERNAL_ERROR, "Erro interno inesperado. Tente novamente.", retryable=True),
        )
