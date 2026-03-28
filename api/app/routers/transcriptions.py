import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.dependencies.auth import require_api_access_token
from app.schemas.transcription import (
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionSegment,
    TranscriptionTask,
)
from app.services.faster_whisper_transcriber import (
    FasterWhisperTranscriptionException,
    FasterWhisperTranscriptionService,
    TranscriptionResult,
)
from app.utils.validators import is_youtube_url

router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])

transcription_service = FasterWhisperTranscriptionService()


def _build_response(result: TranscriptionResult) -> TranscriptionResponse:
    return TranscriptionResponse(
        text=result.text,
        language=result.language,
        duration=result.duration,
        model=result.model,
        device=result.device,
        compute_type=result.compute_type,
        segments=[
            TranscriptionSegment(
                id=segment.id,
                start=segment.start,
                end=segment.end,
                text=segment.text,
            )
            for segment in result.segments
        ],
    )


@router.post(
    "/faster-whisper",
    response_model=TranscriptionResponse,
    summary="Transcribe a YouTube video with faster-whisper on CPU",
    description=(
        "Downloads the best available audio stream from a public YouTube URL, "
        "normalizes it with ffmpeg, and runs faster-whisper using CPU inference only."
    ),
    responses={
        400: {
            "description": "Failed to download audio or run transcription.",
        },
        422: {
            "description": "Invalid payload or unsupported URL format.",
        },
        401: {
            "description": "Missing or invalid API access token when authentication is enabled.",
        },
    },
)
async def create_faster_whisper_transcription(
    payload: TranscriptionRequest,
    _: object = Depends(require_api_access_token),
) -> TranscriptionResponse:
    if not is_youtube_url(payload.url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide a valid YouTube URL.",
        )

    try:
        result = transcription_service.transcribe_youtube_url(
            payload.url,
            language=payload.language,
            task=payload.task,
        )
    except FasterWhisperTranscriptionException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _build_response(result)


@router.post(
    "/faster-whisper/upload",
    response_model=TranscriptionResponse,
    summary="Transcribe an uploaded audio or video file with faster-whisper on CPU",
    description=(
        "Receives an uploaded audio or video file, converts it to mono 16 kHz WAV "
        "with ffmpeg, and runs faster-whisper on CPU. Use task=translate to return "
        "English text from non-English speech."
    ),
    responses={
        400: {
            "description": "Failed to process the uploaded media or run transcription.",
        },
        401: {
            "description": "Missing or invalid API access token when authentication is enabled.",
        },
        422: {
            "description": "Invalid multipart payload.",
        },
    },
)
async def create_faster_whisper_upload_transcription(
    file: UploadFile = File(..., description="Audio or video file to transcribe."),
    language: str | None = Form(default=None),
    task: TranscriptionTask = Form(default="transcribe"),
    _: object = Depends(require_api_access_token),
) -> TranscriptionResponse:
    suffix = Path(file.filename or "upload.bin").suffix
    temp_upload_dir = Path(tempfile.mkdtemp(prefix="yt-upload-")).resolve()
    temp_upload_path = temp_upload_dir / f"source{suffix}"

    try:
        with temp_upload_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = transcription_service.transcribe_uploaded_file(
            temp_upload_path,
            language=language,
            task=task,
        )
    except FasterWhisperTranscriptionException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()
        shutil.rmtree(temp_upload_dir, ignore_errors=True)

    return _build_response(result)
