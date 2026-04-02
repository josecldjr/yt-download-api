from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Any

import imageio_ffmpeg
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, sanitize_filename

from app.core.config import settings
from app.schemas.api_configuration import DownloadQuality

logger = logging.getLogger(__name__)


class YoutubeDownloadException(Exception):
    """Raised when the video cannot be downloaded."""


@dataclass(slots=True)
class DownloadedVideo:
    file_path: Path
    suggested_filename: str
    temp_dir: Path
    width: int | None
    height: int | None
    format_id: str | None
    delivery_strategy: str | None


class YouTubeDownloaderService:
    def download(self, url: str, quality: DownloadQuality) -> DownloadedVideo:
        temp_dir = Path(
            tempfile.mkdtemp(prefix=settings.temp_dir_prefix, dir=None)
        ).resolve()

        try:
            ffmpeg_path = self._resolve_ffmpeg_path()
            ffmpeg_available = ffmpeg_path is not None
            base_options = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "restrictfilenames": False,
                "outtmpl": str(temp_dir / "%(title).200B.%(ext)s"),
                "socket_timeout": settings.request_timeout_seconds,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "web"],
                    }
                },
            }
            if settings.youtube_cookiefile:
                base_options["cookiefile"] = settings.youtube_cookiefile
            if settings.youtube_po_token:
                base_options["extractor_args"]["youtube"]["po_token"] = [settings.youtube_po_token]
            info = self._extract_video_info(url, base_options)

            attempts = self._build_download_attempts(
                info=info,
                base_options=base_options,
                ffmpeg_available=ffmpeg_available,
                ffmpeg_path=ffmpeg_path,
                quality=quality,
            )

            downloaded_info = None
            successful_attempt: dict[str, Any] | None = None
            last_download_error: DownloadError | None = None

            for options in attempts:
                try:
                    with YoutubeDL(options) as ydl:
                        downloaded_info = ydl.extract_info(url, download=True)
                    successful_attempt = options
                    break
                except DownloadError as exc:
                    last_download_error = exc
                    logger.warning(
                        "yt-dlp download attempt failed",
                        extra={
                            "url": url,
                            "quality": quality,
                            "format": options.get("format"),
                            "delivery_strategy": options.get("delivery_strategy"),
                            "error": str(exc),
                        },
                    )
                    self._cleanup_files(temp_dir)

            if downloaded_info is None:
                if last_download_error is not None:
                    raise last_download_error
                raise YoutubeDownloadException("The video could not be downloaded at this time.")

            downloaded_file = self._resolve_downloaded_file(temp_dir)
            title = sanitize_filename(downloaded_info.get("title") or "youtube-video", restricted=False)
            suggested_filename = f"{title}{downloaded_file.suffix}"
            resolution = self._probe_video_resolution(downloaded_file, ffmpeg_path)

            return DownloadedVideo(
                file_path=downloaded_file,
                suggested_filename=suggested_filename,
                temp_dir=temp_dir,
                width=resolution["width"] if resolution else None,
                height=resolution["height"] if resolution else None,
                format_id=str(successful_attempt.get("format")) if successful_attempt else None,
                delivery_strategy=successful_attempt.get("delivery_strategy") if successful_attempt else None,
            )
        except DownloadError as exc:
            self._cleanup(temp_dir)
            logger.exception(
                "yt-dlp failed to download video",
                extra={
                    "url": url,
                    "quality": quality,
                    "error": str(exc),
                },
            )
            raise YoutubeDownloadException(self._normalize_error(exc)) from exc
        except YoutubeDownloadException:
            self._cleanup(temp_dir)
            raise
        except Exception as exc:
            self._cleanup(temp_dir)
            logger.exception(
                "Unexpected failure while processing YouTube download",
                extra={
                    "url": url,
                    "quality": quality,
                },
            )
            raise YoutubeDownloadException("Unexpected failure while processing the download.") from exc

    def cleanup(self, temp_dir: Path) -> None:
        self._cleanup(temp_dir)

    def _resolve_downloaded_file(self, temp_dir: Path) -> Path:
        candidates = [
            path
            for path in temp_dir.iterdir()
            if path.is_file()
            and not path.name.endswith((".part", ".ytdl", ".json", ".description"))
        ]

        if not candidates:
            raise YoutubeDownloadException(
                "No final file was generated. Verify that ffmpeg is installed for videos that require merging."
            )

        return max(candidates, key=lambda item: item.stat().st_size)

    def _normalize_error(self, exc: DownloadError) -> str:
        message = str(exc)
        lowered = message.lower()

        if "ffmpeg is not installed" in lowered or "ffprobe" in lowered:
            return "The API host must have ffmpeg installed to merge separate video and audio streams."
        if "unsupported url" in lowered or "unable to extract" in lowered:
            return "The provided URL could not be processed as a valid YouTube video."
        if "video unavailable" in lowered:
            return "The video is unavailable, private, or region-restricted."
        if "sign in to confirm you're not a bot" in lowered or "confirm you’re not a bot" in lowered:
            return (
                "YouTube blocked this request with a bot-check challenge. "
                "Configure YOUTUBE_COOKIEFILE or YOUTUBE_PO_TOKEN and try again."
            )
        if "http error 403" in lowered or "403: forbidden" in lowered or "forbidden" in lowered:
            return (
                "YouTube denied access to the requested video stream. "
                "This video may require authenticated cookies or a PO token."
            )
        if "requested format is not available" in lowered:
            return (
                "The requested quality is not available for anonymous download on this video. "
                "Try a lower quality or configure YOUTUBE_COOKIEFILE or YOUTUBE_PO_TOKEN."
            )
        if "requested format not available" in lowered:
            return (
                "The requested quality is not available for anonymous download on this video. "
                "Try a lower quality or configure YOUTUBE_COOKIEFILE or YOUTUBE_PO_TOKEN."
            )

        return "The video could not be downloaded at this time."

    def _cleanup(self, temp_dir: Path) -> None:
        shutil.rmtree(temp_dir, ignore_errors=True)

    def _resolve_ffmpeg_path(self) -> str | None:
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg

        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None

    def _probe_video_resolution(
        self,
        file_path: Path,
        ffmpeg_path: str | None,
    ) -> dict[str, int] | None:
        if ffmpeg_path is None:
            return None

        process = subprocess.run(
            [ffmpeg_path, "-i", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        output = process.stderr
        match = re.search(r"Video:.*?,\s(\d+)x(\d+)[,\s]", output)
        if not match:
            return None

        return {
            "width": int(match.group(1)),
            "height": int(match.group(2)),
        }

    def _build_download_attempts(
        self,
        *,
        info: dict[str, Any],
        base_options: dict,
        ffmpeg_available: bool,
        ffmpeg_path: str | None,
        quality: DownloadQuality,
    ) -> list[dict]:
        attempts: list[dict] = []
        target_heights = self._target_heights(info, quality)
        audio_candidates = self._sorted_audio_formats(info)

        for height in target_heights:
            if ffmpeg_available:
                for video_format in self._sorted_video_only_formats(info, height):
                    for audio_format in audio_candidates[:3]:
                        attempts.append(
                            {
                                **base_options,
                                "format": f"{video_format['format_id']}+{audio_format['format_id']}",
                                "ffmpeg_location": ffmpeg_path,
                                "delivery_strategy": f"separate_streams:{height}p",
                            }
                        )

            for progressive_format in self._sorted_progressive_formats(info, height):
                attempts.append(
                    {
                        **base_options,
                        "format": progressive_format["format_id"],
                        "delivery_strategy": f"progressive:{height}p",
                    }
                )

        return attempts

    def _cleanup_files(self, temp_dir: Path) -> None:
        for path in temp_dir.iterdir():
            if path.is_file():
                path.unlink(missing_ok=True)

    def _quality_to_height(self, quality: DownloadQuality) -> int | None:
        mapping = {
            "144p": 144,
            "360p": 360,
            "480p": 480,
            "720p": 720,
            "1080p": 1080,
            "1440p": 1440,
            "4k": 2160,
            "best": None,
        }
        return mapping[quality]

    def _extract_video_info(self, url: str, base_options: dict) -> dict[str, Any]:
        extract_options = {
            **base_options,
            "skip_download": True,
        }
        with YoutubeDL(extract_options) as ydl:
            return ydl.extract_info(url, download=False)

    def _target_heights(self, info: dict[str, Any], quality: DownloadQuality) -> list[int]:
        requested_height = self._quality_to_height(quality)
        available = sorted(
            {
                int(fmt["height"])
                for fmt in info.get("formats", [])
                if fmt.get("height") and fmt.get("vcodec") != "none"
            },
            reverse=True,
        )
        if requested_height is None:
            return available

        within_limit = [height for height in available if height <= requested_height]
        return within_limit or available[-1:]

    def _sorted_video_only_formats(self, info: dict[str, Any], height: int) -> list[dict[str, Any]]:
        formats = [
            fmt
            for fmt in info.get("formats", [])
            if fmt.get("height") == height
            and fmt.get("vcodec") not in (None, "none")
            and fmt.get("acodec") == "none"
        ]
        return sorted(
            formats,
            key=lambda fmt: (
                self._video_ext_rank(fmt.get("ext")),
                -(fmt.get("filesize") or fmt.get("filesize_approx") or 0),
                -(fmt.get("tbr") or 0),
            ),
        )

    def _sorted_progressive_formats(self, info: dict[str, Any], height: int) -> list[dict[str, Any]]:
        formats = [
            fmt
            for fmt in info.get("formats", [])
            if fmt.get("height") == height
            and fmt.get("vcodec") not in (None, "none")
            and fmt.get("acodec") not in (None, "none")
        ]
        return sorted(
            formats,
            key=lambda fmt: (
                self._container_rank(fmt.get("ext")),
                -(fmt.get("filesize") or fmt.get("filesize_approx") or 0),
                -(fmt.get("tbr") or 0),
            ),
        )

    def _sorted_audio_formats(self, info: dict[str, Any]) -> list[dict[str, Any]]:
        formats = [
            fmt
            for fmt in info.get("formats", [])
            if fmt.get("acodec") not in (None, "none") and fmt.get("vcodec") == "none"
        ]
        return sorted(
            formats,
            key=lambda fmt: (
                self._audio_ext_rank(fmt.get("ext")),
                -(fmt.get("abr") or 0),
                -(fmt.get("filesize") or fmt.get("filesize_approx") or 0),
            ),
        )

    def _video_ext_rank(self, ext: str | None) -> int:
        if ext == "mp4":
            return 0
        if ext == "webm":
            return 1
        return 2

    def _audio_ext_rank(self, ext: str | None) -> int:
        if ext in {"m4a", "mp4"}:
            return 0
        if ext == "webm":
            return 1
        return 2

    def _container_rank(self, ext: str | None) -> int:
        if ext == "mp4":
            return 0
        if ext == "webm":
            return 1
        return 2
