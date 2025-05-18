from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger("uvicorn.error")

class CustomHTTPException(Exception):
    """A custom HTTPException that we can use for additional context."""
    def __init__(self, status_code: int, detail: str, error_code: str = None, headers: dict = None):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.headers = headers
        super().__init__(detail)  # Initialize the base Exception with the detail message

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors and return a structured JSON response."""
    logger.error(f"Validation error on {request.url}: {exc.errors()}")

    errors = exc.errors()
    # Sanitize un-serializable objects in ctx
    for error in errors:
        ctx = error.get("ctx")
        if ctx and isinstance(ctx.get("error"), Exception):
            ctx["error"] = str(ctx["error"])

    return JSONResponse(
        status_code=422,
        content={
            "detail": errors,
            "message": "Validation failed. Please check your request data.",
        },
    )

async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Custom HTTP exception handler for better error responses."""
    if isinstance(exc, CustomHTTPException):
        logger.error(f"Custom HTTP error on {request.url}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code
            },
            headers=exc.headers or {},
        )
    elif isinstance(exc, HTTPException):
        logger.error(f"HTTP error on {request.url}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {},
        )

    logger.error(f"Unexpected error on {request.url}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"},
    )
