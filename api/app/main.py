from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models.access_token import AccessToken  # noqa: F401
from app.models.api_configuration import ApiConfiguration  # noqa: F401
from app.routers.admin_tokens import router as admin_tokens_router
from app.routers.api_configuration import admin_router as admin_api_configuration_router
from app.routers.api_configuration import router as api_configuration_router
from app.routers.downloads import router as downloads_router

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"
MANAGE_FILE = FRONTEND_DIR / "manage.html"

openapi_tags = [
    {
        "name": "health",
        "description": "Endpoints for API availability and health checks.",
    },
    {
        "name": "downloads",
        "description": "Endpoints to request and download YouTube videos.",
    },
    {
        "name": "admin",
        "description": "Protected endpoints for API management and access token administration.",
    },
    {
        "name": "settings",
        "description": "Public application settings consumed by the frontend.",
    },
]

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "REST API for downloading YouTube videos. "
        "It receives a public URL, processes the video with yt-dlp, and returns "
        "the file as a stream with the appropriate download headers."
    ),
    docs_url="/api-docs",
    openapi_url="/api-docs/openapi.json",
    redoc_url=None,
    openapi_tags=openapi_tags,
    contact={
        "name": "YT Download API Team",
        "url": "https://github.com/josecldjr/yt-download-api",
    },
    license_info={
        "name": "Proprietary",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Content-Disposition",
        "Content-Length",
        "Content-Type",
        "X-Video-Width",
        "X-Video-Height",
        "X-Video-Resolution",
        "X-Video-Format-Id",
        "X-Video-Delivery-Strategy",
    ],
)


@app.on_event("startup")
async def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)


@app.get(
    "/health",
    tags=["health"],
    summary="Application health check",
    description="Returns the API status for monitoring, probes, and load balancers.",
)
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def serve_frontend() -> FileResponse:
    return FileResponse(
        INDEX_FILE,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/index.html", include_in_schema=False)
async def serve_frontend_index() -> FileResponse:
    return await serve_frontend()


@app.get("/manage", include_in_schema=False)
async def serve_management_page() -> FileResponse:
    return FileResponse(
        MANAGE_FILE,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/manage.html", include_in_schema=False)
async def serve_management_page_index() -> FileResponse:
    return await serve_management_page()


app.include_router(downloads_router, prefix=settings.api_prefix)
app.include_router(admin_tokens_router, prefix=settings.api_prefix)
app.include_router(api_configuration_router, prefix=settings.api_prefix)
app.include_router(admin_api_configuration_router, prefix=settings.api_prefix)
