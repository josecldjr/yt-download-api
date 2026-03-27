from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import settings
from app.routers.downloads import router as downloads_router

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"

openapi_tags = [
    {
        "name": "health",
        "description": "Endpoints de verificação de disponibilidade da API.",
    },
    {
        "name": "downloads",
        "description": "Endpoints para solicitar e baixar vídeos do YouTube.",
    },
]

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "API REST para download de vídeos do YouTube. "
        "Recebe uma URL pública, processa o vídeo com yt-dlp e devolve o arquivo "
        "via stream com headers apropriados para download."
    ),
    docs_url="/api-docs",
    openapi_url="/api-docs/openapi.json",
    redoc_url=None,
    openapi_tags=openapi_tags,
    contact={
        "name": "Equipe YT Download API",
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
    expose_headers=["Content-Disposition", "Content-Length", "Content-Type"],
)


@app.get(
    "/health",
    tags=["health"],
    summary="Healthcheck da aplicação",
    description="Retorna o status da API para uso em monitoração, probes e balanceadores.",
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


app.include_router(downloads_router, prefix=settings.api_prefix)
