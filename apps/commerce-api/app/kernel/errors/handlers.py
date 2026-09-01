import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.kernel.errors.exceptions import CruxNexusError
from app.kernel.errors.responses import error_response

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CruxNexusError)
    async def cruxnexus_error_handler(request: Request, exc: CruxNexusError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        status_code = status.HTTP_409_CONFLICT if "CAPACITY" in exc.code else status.HTTP_400_BAD_REQUEST
        if "NOT_FOUND" in exc.code:
            status_code = status.HTTP_404_NOT_FOUND
        if exc.code in {"TENANT_ACCESS_DENIED", "FORBIDDEN", "MEMBERSHIP_REQUIRED", "MERCHANT_REQUIRED"}:
            status_code = status.HTTP_403_FORBIDDEN
        return JSONResponse(
            status_code=status_code,
            content=error_response(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=request_id,
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                code="HTTP_ERROR",
                message=str(detail),
                request_id=request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                request_id=request_id,
            ),
        )
