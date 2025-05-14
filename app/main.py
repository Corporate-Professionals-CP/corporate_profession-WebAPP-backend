import logging
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.openapi.utils import get_openapi
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.db.database import init_db, async_engine
from app.api import auth, admin, bookmarks, certification, comments, contacts, directory, education, feed, follow, notification, posts, post_reaction, profiles, skill, skill_catalog, volunteering, work_experiences
from app.core.exceptions import validation_exception_handler, http_exception_handler
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request



logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await async_engine.dispose()

app = FastAPI(
    title=settings.PROJECT_TITLE,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."}
    )

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
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

# API Routers
api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(admin.router, tags=["Admin"])
api_router.include_router(bookmarks.router, tags=["bookmarks"])
api_router.include_router(certification.router, tags=["certification"])
api_router.include_router(comments.router, tags=["Comments"])
api_router.include_router(contacts.router, tags=["contacts"])
api_router.include_router(directory.router, tags=["Directory"])
api_router.include_router(education.router, tags=["education"])
api_router.include_router(feed.router, tags=["feed"])
api_router.include_router(follow.router, tags=["follow"])
api_router.include_router(notification.router, tags=["notifications"])
api_router.include_router(posts.router, tags=["Posts"])
api_router.include_router(profiles.router, tags=["Profiles"])
api_router.include_router(post_reaction.router, tags=["Post Reactions"])
api_router.include_router(skill.router, tags=["skill"])
api_router.include_router(skill_catalog.router, tags=["skills"])
api_router.include_router(volunteering.router, tags=["volunteering"])
api_router.include_router(work_experiences.router, tags=["Work Experiences"])
app.include_router(api_router)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.PROJECT_TITLE,
        version=settings.PROJECT_VERSION,
        description=settings.PROJECT_DESCRIPTION,
        routes=app.routes,
    )

    # Add security scheme without overwriting existing components
    security_scheme = {
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": "/api/auth/token",
                    "scopes": {
                        "user": "Regular user access",
                        "recruiter": "Recruiter privileges",
                        "admin": "Admin privileges"
                    }
                }
            }
        }
    }

    # Merge security scheme with existing components
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {}).update(security_scheme)

    # Add security requirements to operations
    for path in openapi_schema["paths"].values():
        for operation in path.values():
            if any(tag in operation.get("tags", []) for tag in ["Profiles", "Posts", "Directory", "Admin"]):
                operation.setdefault("security", []).append({"OAuth2PasswordBearer": []})

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/", include_in_schema=False)
async def health_check():
    return {
        "status": "healthy",
        "version": settings.PROJECT_VERSION,
        "docs": "/docs"
    }
