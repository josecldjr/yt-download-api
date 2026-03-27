import mimetypes

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse

from app.dependencies.auth import require_api_access_token
from app.schemas.download import DownloadRequest
from app.services.api_configuration import QUALITY_OPTIONS
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
        "can trigger the browser download. Quality can be capped at one of the "
        f"supported values: {', '.join(QUALITY_OPTIONS)}."
    ),
    responses={
        200: {
            "description": "Video file returned successfully.",
            "headers": {
                "X-Video-Width": {
                    "description": "Final delivered video width in pixels.",
                    "schema": {"type": "integer"},
                },
                "X-Video-Height": {
                    "description": "Final delivered video height in pixels.",
                    "schema": {"type": "integer"},
                },
                "X-Video-Resolution": {
                    "description": "Final delivered video resolution formatted as WIDTHxHEIGHT.",
                    "schema": {"type": "string"},
                },
                "X-Video-Format-Id": {
                    "description": "yt-dlp format id or merged format ids used to deliver the final file.",
                    "schema": {"type": "string"},
                },
                "X-Video-Delivery-Strategy": {
                    "description": "Download strategy that succeeded, such as separate streams or progressive fallback.",
                    "schema": {"type": "string"},
                },
            },
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
        401: {
            "description": "Missing or invalid API access token when authentication is enabled.",
            "content": {
                "application/json": {
                    "examples": {
                        "missing": {
                            "summary": "Missing token",
                            "value": {
                                "detail": "A valid API access token is required."
                            },
                        },
                        "invalid": {
                            "summary": "Invalid token",
                            "value": {
                                "detail": "Invalid API access token."
                            },
                        },
                    }
                }
            },
        },
    },
)
async def create_download(
    payload: DownloadRequest,
    background_tasks: BackgroundTasks,
    _: object = Depends(require_api_access_token),
) -> FileResponse:
    if not is_youtube_url(payload.url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide a valid YouTube URL.",
        )

    try:
        downloaded_video = downloader_service.download(payload.url, payload.quality)
    except YoutubeDownloadException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    background_tasks.add_task(downloader_service.cleanup, downloaded_video.temp_dir)
    media_type = mimetypes.guess_type(downloaded_video.file_path.name)[0] or "application/octet-stream"
    response_headers: dict[str, str] = {}
    if downloaded_video.width is not None:
        response_headers["X-Video-Width"] = str(downloaded_video.width)
    if downloaded_video.height is not None:
        response_headers["X-Video-Height"] = str(downloaded_video.height)
    if downloaded_video.width is not None and downloaded_video.height is not None:
        response_headers["X-Video-Resolution"] = f"{downloaded_video.width}x{downloaded_video.height}"
    if downloaded_video.format_id:
        response_headers["X-Video-Format-Id"] = downloaded_video.format_id
    if downloaded_video.delivery_strategy:
        response_headers["X-Video-Delivery-Strategy"] = downloaded_video.delivery_strategy

    return FileResponse(
        path=downloaded_video.file_path,
        filename=downloaded_video.suggested_filename,
        media_type=media_type,
        background=background_tasks,
        headers=response_headers,
    )
