from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.api_configuration import get_max_transcription_upload_size_bytes


class PayloadTooLargeError(Exception):
    """Raised when a request body exceeds the configured upload limit."""


class TranscriptionUploadLimitMiddleware:
    def __init__(self, app: Callable) -> None:
        self.app = app
        self._upload_path = f"{settings.api_prefix}/transcriptions/faster-whisper/upload"

    async def __call__(self, scope: dict, receive: Callable[[], Awaitable[dict]], send: Callable[[dict], Awaitable[None]]) -> None:
        if scope.get("type") != "http" or not self._matches_upload_endpoint(scope):
            await self.app(scope, receive, send)
            return

        max_size_bytes = self._load_max_size_bytes()
        bytes_seen = 0

        async def limited_receive() -> dict:
            nonlocal bytes_seen
            message = await receive()
            if message["type"] != "http.request":
                return message

            body = message.get("body", b"")
            bytes_seen += len(body)
            if bytes_seen > max_size_bytes:
                raise PayloadTooLargeError(
                    f"Upload exceeds the configured limit of {max_size_bytes // (1024 * 1024)} MB."
                )

            return message

        try:
            await self.app(scope, limited_receive, send)
        except PayloadTooLargeError as exc:
            response = JSONResponse(
                status_code=413,
                content={"detail": str(exc)},
            )
            await response(scope, receive, send)

    def _matches_upload_endpoint(self, scope: dict) -> bool:
        return (
            scope.get("method") == "POST"
            and scope.get("path") == self._upload_path
        )

    def _load_max_size_bytes(self) -> int:
        session = SessionLocal()
        try:
            return get_max_transcription_upload_size_bytes(session)
        finally:
            session.close()
