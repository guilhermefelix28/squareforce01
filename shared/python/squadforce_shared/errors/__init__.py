"""Erros padronizados da API: código estável, mensagem, possibilidade de repetição e detalhes."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    # Genéricos
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # Idempotência / concorrência
    IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    REQUEST_IN_PROGRESS = "REQUEST_IN_PROGRESS"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    # Importações
    UNSUPPORTED_FILE = "UNSUPPORTED_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_WORKBOOK = "INVALID_WORKBOOK"
    IMPORT_VALIDATION_FAILED = "IMPORT_VALIDATION_FAILED"
    IMPORT_BLOCKED_ACTIVE_COMPETITION = "IMPORT_BLOCKED_ACTIVE_COMPETITION"
    IMPORT_IN_PROGRESS = "IMPORT_IN_PROGRESS"
    IMPORT_FAILED = "IMPORT_FAILED"
    # Sessões
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_ALREADY_ACTIVE = "SESSION_ALREADY_ACTIVE"
    SESSION_CLOSED = "SESSION_CLOSED"
    INVALID_COMPETITION_CONFIG = "INVALID_COMPETITION_CONFIG"
    CLUB_NOT_FOUND = "CLUB_NOT_FOUND"
    CLUB_NOT_ELIGIBLE = "CLUB_NOT_ELIGIBLE"
    COMPETITION_PLANNING_FAILED = "COMPETITION_PLANNING_FAILED"
    CATALOG_EMPTY = "CATALOG_EMPTY"


class AppError(Exception):
    """Erro de aplicação convertido pelo gateway em resposta JSON padronizada."""

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

    def to_body(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "retryable": self.retryable,
                "details": self.details,
            }
        }
