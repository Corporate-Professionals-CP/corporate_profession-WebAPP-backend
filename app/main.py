"""
Main FastAPI application configuration
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.config import settings
from app.db.database import init_db, async_engine
from app.api import (
    auth,
    profiles,
    directory,
    posts,
    admin,
    feed
)
from app.core.exceptions import (
    validation_exception_handler,
    http_exception_handler
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application services"""
    # Create upload directory if it doesn't exist
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Create database tables
    await init_db()
    yield
    # Clean up resources
    await async_engine.dispose()

app = FastAPI(
    title=settings.PROJECT_TITLE,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    openapi_url=settings.OPENAPI_URL,
    docs_url=settings.DOCS_URL,
    lifespan=lifespan
)

# Mount static files for CV downloads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

# API Routers
api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(profiles.router, tags=["Profiles"])
api_router.include_router(directory.router, tags=["Directory"])
api_router.include_router(posts.router, tags=["Posts"])
api_router.include_router(admin.router, tags=["Admin"])
api_router.include_router(feed.router, tags=["Feed"])

app.include_router(api_router)

@app.get("/", include_in_schema=False)
async def health_check() -> dict:
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.PROJECT_VERSION,
        "docs": f"{settings.DOCS_URL}"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )