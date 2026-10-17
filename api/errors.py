"""One error format for every failure: {"error": {"code", "message", "request_id"}}.

422 responses also list which fields failed (location, message, type), but never
the submitted values, so a client's transaction is not echoed back.
"""
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    404: "not_found",
    405: "method_not_allowed",
    422: "validation_error",
    500: "internal_error",
    503: "service_unavailable",
}


def error_response(request: Request, status: int, message: str, code: str | None = None,
                   details: list | None = None) -> JSONResponse:
    code = code or ERROR_CODES.get(status, HTTPStatus(status).phrase.lower().replace(" ", "_"))
    request.state.error_code = code  # picked up by the request log line
    error = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status, content={"error": error})


def validation_details(exc: RequestValidationError) -> list[dict]:
    return [
        {"loc": list(e["loc"]), "message": e["msg"], "type": e["type"]}
        for e in exc.errors()
    ]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def on_validation_error(request: Request, exc: RequestValidationError):
        details = validation_details(exc)
        request.state.error_fields = [".".join(map(str, d["loc"])) for d in details]
        return error_response(request, 422, "Request body failed validation", details=details)

    @app.exception_handler(StarletteHTTPException)
    async def on_http_error(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        response = error_response(request, exc.status_code, message)
        for key, value in (exc.headers or {}).items():  # e.g. Allow on a 405
            response.headers[key] = value
        return response
