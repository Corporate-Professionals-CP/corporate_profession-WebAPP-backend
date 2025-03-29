from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.db.database import create_db_and_tables
from app.api import auth, profiles, directory, posts, admin, feed
from app.core.exceptions import validation_exception_handler, http_exception_handler

app = FastAPI(
    title=settings.PROJECT_TITLE,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    openapi_url=settings.OPENAPI_URL,
)

# Register custom exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

@app.on_event("startup")
def on_startup() -> None:
    # Create database tables at startup
    create_db_and_tables()

# Include routers with appropriate prefixes and tags
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["Profiles"])
app.include_router(directory.router, prefix="/api/directory", tags=["Directory"])
app.include_router(posts.router, prefix="/api/posts", tags=["Posts"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(feed.router, prefix="/api/feed", tags=["Feed"])

@app.get("/")
async def root() -> dict:
    return {"message": "Welcome to the Corporate Professionals WebApp Backend API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

