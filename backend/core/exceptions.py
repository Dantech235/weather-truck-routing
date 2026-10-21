"""Uniform API error shape: {"error": {"code", "message", "field"}}."""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    NotFound,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler


class ApiError(Exception):
    """Domain error raised by services and views; rendered by `api_exception_handler`."""

    def __init__(
        self,
        code: str,
        message: str,
        field: str | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.status_code = status_code


def error_body(code: str, message: str, field: str | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "field": field}}


def _first_validation_error(detail: Any, prefix: str = "") -> tuple[str | None, str]:
    """Walk a DRF ValidationError detail and return (dotted field path, first message)."""
    if isinstance(detail, dict):
        for key, value in detail.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            field, message = _first_validation_error(value, path)
            name = None if key == "non_field_errors" else field
            return name, message
    if isinstance(detail, list) and detail:
        return _first_validation_error(detail[0], prefix)
    return (prefix or None), str(detail)


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, ApiError):
        return Response(error_body(exc.code, exc.message, exc.field), status=exc.status_code)

    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, ValidationError):
        field, message = _first_validation_error(exc.detail)
        response.data = error_body("VALIDATION_ERROR", message, field)
    elif isinstance(exc, Throttled):
        response.data = error_body("RATE_LIMITED", "Too many requests. Try again shortly.")
        wait: float | None = getattr(exc, "wait", None)  # set at runtime; missing from stubs
        if wait is not None:
            response["Retry-After"] = str(int(wait) + 1)
    elif isinstance(exc, NotFound):
        response.data = error_body("NOT_FOUND", str(exc.detail))
    elif isinstance(exc, APIException):
        code = exc.default_code.upper() if isinstance(exc.default_code, str) else "ERROR"
        response.data = error_body(code, str(exc.detail))
    return response
