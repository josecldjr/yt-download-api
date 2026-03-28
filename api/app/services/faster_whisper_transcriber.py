from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
from faster_whisper import WhisperModel
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.core.config import settings


class FasterWhisperTranscriptionException(Exception):
    """Raised when audio extraction or transcription fails."""


@dataclass(slots=True)
class TranscriptionSegmentData:
    id: int
    start: float
    end: float
    text: str


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    language: str
    duration: float
    model: str
    device: str
    compute_type: str
    segments: list[TranscriptionSegmentData]


class FasterWhisperTranscriptionService:
    def __init__(self) -> None:
        self._models: dict[str, WhisperModel] = {}

    def transcribe_youtube_url(
        self,
        url: str,
        *,
        language: str | None,
        task: str,
        model_name: str | None,
    ) -> TranscriptionResult:
        temp_dir = Path(tempfile.mkdtemp(prefix=settings.temp_dir_prefix, dir=None)).resolve()

        try:
            audio_file = self._download_audio(url, temp_dir)
            prepared_audio = self._prepare_audio_for_whisper(audio_file, temp_dir)
            return self._transcribe_file(
                prepared_audio,
                language=language,
                task=task,
                model_name=model_name,
            )
        except DownloadError as exc:
            raise FasterWhisperTranscriptionException(
                self._normalize_download_error(exc)
            ) from exc
        except FasterWhisperTranscriptionException:
            raise
        except Exception as exc:
            raise FasterWhisperTranscriptionException(
                "Unexpected failure while transcribing the requested video."
            ) from exc
        finally:
            self.cleanup(temp_dir)

    def transcribe_uploaded_file(
        self,
        source_file: Path,
        *,
        language: str | None,
        task: str,
        model_name: str | None,
    ) -> TranscriptionResult:
        temp_dir = Path(tempfile.mkdtemp(prefix=settings.temp_dir_prefix, dir=None)).resolve()

        try:
            input_path = temp_dir / source_file.name
            shutil.copy2(source_file, input_path)
            prepared_audio = self._prepare_audio_for_whisper(input_path, temp_dir)
            return self._transcribe_file(
                prepared_audio,
                language=language,
                task=task,
                model_name=model_name,
            )
        except FasterWhisperTranscriptionException:
            raise
        except Exception as exc:
            raise FasterWhisperTranscriptionException(
                "Unexpected failure while transcribing the uploaded file."
            ) from exc
        finally:
            self.cleanup(temp_dir)

    def cleanup(self, temp_dir: Path) -> None:
        shutil.rmtree(temp_dir, ignore_errors=True)

    def _transcribe_file(
        self,
        audio_file: Path,
        *,
        language: str | None,
        task: str,
        model_name: str | None,
    ) -> TranscriptionResult:
        selected_model_name = model_name or settings.faster_whisper_model
        model = self._get_model(selected_model_name)
        segments, info = model.transcribe(
            str(audio_file),
            language=language,
            task=task,
            vad_filter=True,
        )

        normalized_segments = [
            TranscriptionSegmentData(
                id=index,
                start=segment.start,
                end=segment.end,
                text=segment.text.strip(),
            )
            for index, segment in enumerate(segments)
        ]

        return TranscriptionResult(
            text=" ".join(
                segment.text for segment in normalized_segments if segment.text
            ).strip(),
            language=info.language or language or "unknown",
            duration=info.duration or 0.0,
            model=selected_model_name,
            device=settings.faster_whisper_device,
            compute_type=settings.faster_whisper_compute_type,
            segments=normalized_segments,
        )

    def _prepare_audio_for_whisper(self, input_file: Path, temp_dir: Path) -> Path:
        ffmpeg_path = self._resolve_ffmpeg_path()
        if ffmpeg_path is None:
            raise FasterWhisperTranscriptionException(
                "The API host must have ffmpeg installed to prepare audio for transcription."
            )

        output_file = temp_dir / "whisper-input.wav"
        process = subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                str(input_file),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode != 0 or not output_file.exists():
            raise FasterWhisperTranscriptionException(
                "Failed to convert the uploaded media into a Whisper-compatible audio format."
            )

        return output_file

    def _get_model(self, model_name: str) -> WhisperModel:
        if settings.faster_whisper_device != "cpu":
            raise FasterWhisperTranscriptionException(
                "This endpoint is configured to run only with CPU. Set FASTER_WHISPER_DEVICE=cpu."
            )

        if model_name not in self._models:
            model_kwargs: dict[str, object] = {
                "device": settings.faster_whisper_device,
                "compute_type": settings.faster_whisper_compute_type,
            }
            if settings.faster_whisper_cpu_threads > 0:
                model_kwargs["cpu_threads"] = settings.faster_whisper_cpu_threads

            self._models[model_name] = WhisperModel(
                model_name,
                **model_kwargs,
            )

        return self._models[model_name]

    def _resolve_ffmpeg_path(self) -> str | None:
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg

        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None

    def _download_audio(self, url: str, temp_dir: Path) -> Path:
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": False,
            "format": "bestaudio/best",
            "outtmpl": str(temp_dir / "%(title).200B.%(ext)s"),
            "socket_timeout": settings.request_timeout_seconds,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                }
            },
        }
        if settings.youtube_cookiefile:
            options["cookiefile"] = settings.youtube_cookiefile
        if settings.youtube_po_token:
            options["extractor_args"]["youtube"]["po_token"] = [settings.youtube_po_token]

        with YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)

        candidates = [
            path
            for path in temp_dir.iterdir()
            if path.is_file()
            and not path.name.endswith((".part", ".ytdl", ".json", ".description"))
        ]
        if not candidates:
            raise FasterWhisperTranscriptionException(
                "No audio file was generated for transcription."
            )

        return max(candidates, key=lambda item: item.stat().st_size)

    def _normalize_download_error(self, exc: DownloadError) -> str:
        message = str(exc).lower()

        if "unsupported url" in message or "unable to extract" in message:
            return "The provided URL could not be processed as a valid YouTube video."
        if "video unavailable" in message:
            return "The video is unavailable, private, or region-restricted."

        return "The audio could not be downloaded for transcription at this time."
