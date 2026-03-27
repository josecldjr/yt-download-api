import mimetypes

from fastapi import APIRouter, HTTPException, status
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse

from app.schemas.download import DownloadRequest
from app.services.youtube_downloader import (
    YouTubeDownloaderService,
    YoutubeDownloadException,
)
from app.utils.validators import is_youtube_url

router = APIRouter(prefix="/downloads", tags=["downloads"])

downloader_service = YouTubeDownloaderService()


@router.post(
    "",
    response_class=FileResponse,
    summary="Baixar vídeo do YouTube",
    description=(
        "Recebe uma URL pública do YouTube, valida a entrada, faz o download do vídeo "
        "e retorna o arquivo com `Content-Disposition: attachment` para disparar o "
        "download no cliente."
    ),
    responses={
        200: {
            "description": "Arquivo de vídeo retornado com sucesso.",
            "content": {
                "video/mp4": {
                    "schema": {
                        "type": "string",
                        "format": "binary",
                    }
                },
                "application/octet-stream": {
                    "schema": {
                        "type": "string",
                        "format": "binary",
                    }
                },
            },
        },
        400: {
            "description": "Falha ao processar ou baixar o vídeo.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Não foi possível baixar este vídeo no momento."
                    }
                }
            },
        },
        422: {
            "description": "Payload inválido ou URL fora do padrão esperado.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Informe uma URL válida do YouTube."
                    }
                }
            },
        },
    },
)
async def create_download(
    payload: DownloadRequest, background_tasks: BackgroundTasks
) -> FileResponse:
    if not is_youtube_url(payload.url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe uma URL válida do YouTube.",
        )

    try:
        downloaded_video = downloader_service.download(payload.url)
    except YoutubeDownloadException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    background_tasks.add_task(downloader_service.cleanup, downloaded_video.temp_dir)
    media_type = mimetypes.guess_type(downloaded_video.file_path.name)[0] or "application/octet-stream"

    return FileResponse(
        path=downloaded_video.file_path,
        filename=downloaded_video.suggested_filename,
        media_type=media_type,
        background=background_tasks,
    )
