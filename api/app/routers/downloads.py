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
    summary="Download a YouTube video",
    description=(
        "Receives a public YouTube URL, validates the input, downloads the video, "
        "and returns the file with `Content-Disposition: attachment` so the client "
        "can trigger the browser download."
    ),
    responses={
        200: {
            "description": "Video file returned successfully.",
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
            "description": "Failed to process or download the video.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "The video could not be downloaded at this time."
                    }
                }
            },
        },
        422: {
            "description": "Invalid payload or unsupported URL format.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Provide a valid YouTube URL."
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
            detail="Provide a valid YouTube URL.",
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
