from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, sanitize_filename

from app.core.config import settings


class YoutubeDownloadException(Exception):
    """Raised when the video cannot be downloaded."""


@dataclass(slots=True)
class DownloadedVideo:
    file_path: Path
    suggested_filename: str
    temp_dir: Path


class YouTubeDownloaderService:
    def download(self, url: str) -> DownloadedVideo:
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
                raise YoutubeDownloadException("Não foi possível baixar este vídeo no momento.")

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
            raise YoutubeDownloadException("Falha inesperada ao processar o download.") from exc

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
                "Nenhum arquivo final foi gerado. Verifique se o ffmpeg está instalado para vídeos que exigem mesclagem."
            )

        return max(candidates, key=lambda item: item.stat().st_size)

    def _normalize_error(self, exc: DownloadError) -> str:
        message = str(exc)
        lowered = message.lower()

        if "ffmpeg is not installed" in lowered or "ffprobe" in lowered:
            return "O host da API precisa ter ffmpeg instalado para mesclar vídeo e áudio em formatos separados."
        if "unsupported url" in lowered or "unable to extract" in lowered:
            return "A URL informada não pôde ser processada como um vídeo válido do YouTube."
        if "video unavailable" in lowered:
            return "O vídeo está indisponível, privado ou com restrição regional."

        return "Não foi possível baixar este vídeo no momento."

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
    ) -> list[dict]:
        attempts: list[dict] = []

        if ffmpeg_available:
            attempts.append(
                {
                    **base_options,
                    "format": (
                        "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]"
                        "/best[ext=mp4][height<=1080]"
                        "/best[height<=1080]"
                    ),
                    "merge_output_format": "mp4",
                    "ffmpeg_location": ffmpeg_path,
                }
            )

        # Progressive fallback avoids merging and often survives YouTube's
        # restrictions for videos where DASH URLs return 403.
        attempts.append(
            {
                **base_options,
                "format": (
                    "best[ext=mp4][acodec!=none][vcodec!=none][height<=1080]"
                    "/18"
                    "/best[acodec!=none][vcodec!=none][height<=1080]"
                    "/best"
                ),
            }
        )

        return attempts

    def _cleanup_files(self, temp_dir: Path) -> None:
        for path in temp_dir.iterdir():
            if path.is_file():
                path.unlink(missing_ok=True)
