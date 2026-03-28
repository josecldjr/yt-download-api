from typing import Literal

from pydantic import BaseModel, Field


class TranscriptionRequest(BaseModel):
    url: str = Field(
        ...,
        description="Public YouTube video URL.",
        examples=[
            "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        ],
    )
    language: str | None = Field(
        default=None,
        description="Optional source language code such as en, pt, or es. If omitted, the model will auto-detect.",
        examples=["pt", "en"],
    )
    task: Literal["transcribe", "translate"] = Field(
        default="transcribe",
        description="Whether to return speech in the original language or translate it to English.",
        examples=["transcribe", "translate"],
    )


class TranscriptionSegment(BaseModel):
    id: int = Field(..., description="Sequential segment identifier.")
    start: float = Field(..., description="Segment start time in seconds.")
    end: float = Field(..., description="Segment end time in seconds.")
    text: str = Field(..., description="Recognized text for the segment.")


class TranscriptionResponse(BaseModel):
    text: str = Field(..., description="Full transcript text.")
    language: str = Field(..., description="Detected or selected source language.")
    duration: float = Field(..., description="Audio duration in seconds.")
    model: str = Field(..., description="Whisper model name used by the server.")
    device: str = Field(..., description="Execution device used for inference.")
    compute_type: str = Field(..., description="Inference compute type.")
    segments: list[TranscriptionSegment] = Field(
        default_factory=list,
        description="Timestamped transcript segments.",
    )


class FileTranscriptionRequest(BaseModel):
    language: str | None = Field(
        default=None,
        description="Optional source language code such as en, pt, or es. If omitted, the model will auto-detect.",
        examples=["pt", "en"],
    )
    task: Literal["transcribe", "translate"] = Field(
        default="transcribe",
        description="Whether to return speech in the original language or translate it to English.",
        examples=["transcribe", "translate"],
    )
