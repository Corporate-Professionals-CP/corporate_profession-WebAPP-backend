from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.openapi.utils import get_openapi
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.db.database import init_db, async_engine
from app.api import auth, profiles, directory, posts, admin, feed
from app.core.exceptions import validation_exception_handler, http_exception_handler

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
