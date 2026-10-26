"""Domain errors and their mapping to RFC 9457 problem+json responses."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

log = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(
        self, detail: str = "", *, code: str | None = None, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.headers = headers or {}
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, detail: str, *, retry_after: int) -> None:
        super().__init__(detail, headers={"Retry-After": str(retry_after)})
        self.retry_after = retry_after


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_unavailable"


def _problem(status: int, code: str, detail: str, **extra: object) -> JSONResponse:
    body = {
        "type": f"https://mealfinder.dev/problems/{code}",
        "title": code.replace("_", " ").capitalize(),
        "status": status,
        "detail": detail,
        "request_id": request_id_var.get(),
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    response = _problem(exc.status_code, exc.code, exc.detail)
    response.headers.update(exc.headers)
    return response


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    # Framework-raised errors such as unknown routes (404) and wrong methods (405).
    assert isinstance(exc, StarletteHTTPException)
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    response = _problem(exc.status_code, code, str(exc.detail))
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Only the JSON-safe parts: `ctx` can hold the raw exception a validator raised.
    errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return _problem(422, "validation_error", "Request validation failed", errors=errors)


async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error", exc_info=exc)
    return _problem(500, "internal_error", "Something went wrong")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)
