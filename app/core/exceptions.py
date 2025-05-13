from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger("uvicorn.error")

class CustomHTTPException(HTTPException):
    """A custom HTTPException that we can use for additional context."""
    def __init__(self, status_code: int, detail: str, error_code: str = None):
        self.error_code = error_code
        super().__init__(status_code=status_code, detail=detail)

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
        content={"detail": errors, "body": exc.body},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Custom HTTP exception handler for better error responses."""
    logger.error(f"HTTP error on {request.url}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": getattr(exc, 'error_code', None)},
    )

