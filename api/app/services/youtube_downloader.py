from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, sanitize_filename

from app.core.config import settings
from app.schemas.api_configuration import DownloadQuality


class YoutubeDownloadException(Exception):
    """Raised when the video cannot be downloaded."""


@dataclass(slots=True)
class DownloadedVideo:
    file_path: Path
    suggested_filename: str
    temp_dir: Path


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
                        "formats": ["missing_pot"],
                    }
                },
            }

            attempts = self._build_download_attempts(
                base_options=base_options,
                ffmpeg_available=ffmpeg_available,
                ffmpeg_path=ffmpeg_path,
                quality=quality,
            )

            info = None
            last_download_error: DownloadError | None = None

            for options in attempts:
                try:
                    with YoutubeDL(options) as ydl:
                        info = ydl.extract_info(url, download=True)
                    break
                except DownloadError as exc:
                    last_download_error = exc
                    self._cleanup_files(temp_dir)

            if info is None:
                if last_download_error is not None:
                    raise last_download_error
                raise YoutubeDownloadException("The video could not be downloaded at this time.")

            downloaded_file = self._resolve_downloaded_file(temp_dir)
            title = sanitize_filename(info.get("title") or "youtube-video", restricted=False)
            suggested_filename = f"{title}{downloaded_file.suffix}"

            return DownloadedVideo(
                file_path=downloaded_file,
                suggested_filename=suggested_filename,
                temp_dir=temp_dir,
            )
        except DownloadError as exc:
            self._cleanup(temp_dir)
            raise YoutubeDownloadException(self._normalize_error(exc)) from exc
        except Exception as exc:
            self._cleanup(temp_dir)
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

    def _build_download_attempts(
        self,
        *,
        base_options: dict,
        ffmpeg_available: bool,
        ffmpeg_path: str | None,
        quality: DownloadQuality,
    ) -> list[dict]:
        attempts: list[dict] = []
        height_limit = self._quality_to_height(quality)
        dash_selector = self._build_dash_selector(height_limit)
        progressive_selector = self._build_progressive_selector(height_limit)

        if ffmpeg_available:
            attempts.append(
                {
                    **base_options,
                    "format": dash_selector,
                    "merge_output_format": "mp4",
                    "ffmpeg_location": ffmpeg_path,
                }
            )

        # Progressive fallback avoids merging and often survives YouTube
        # restrictions for videos where DASH URLs return 403.
        attempts.append(
            {
                **base_options,
                "format": progressive_selector,
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

    def _build_dash_selector(self, height_limit: int | None) -> str:
        if height_limit is None:
            return "bestvideo+bestaudio/best"

        return (
            f"bestvideo[height<={height_limit}]+bestaudio"
            f"/best[height<={height_limit}]"
            "/best"
        )

    def _build_progressive_selector(self, height_limit: int | None) -> str:
        if height_limit is None:
            return "best[ext=mp4][acodec!=none][vcodec!=none]/best[acodec!=none][vcodec!=none]/best"

        return (
            f"best[ext=mp4][acodec!=none][vcodec!=none][height<={height_limit}]"
            f"/best[acodec!=none][vcodec!=none][height<={height_limit}]"
            "/18"
            "/best"
        )
