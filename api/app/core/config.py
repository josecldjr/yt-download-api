import os
from pathlib import Path
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str
    api_prefix: str
    allowed_origins: list[str]
    temp_dir_prefix: str
    request_timeout_seconds: int
    database_url: str
    management_secret: str
    token_encryption_key: str
    youtube_cookiefile: str | None
    youtube_po_token: str | None
    faster_whisper_model: str
    faster_whisper_device: str
    faster_whisper_compute_type: str
    faster_whisper_cpu_threads: int


def _derive_fernet_key(secret: str) -> str:
    digest = sha256(secret.encode("utf-8")).digest()
    return urlsafe_b64encode(digest).decode("utf-8")


def _normalize_fernet_key(value: str) -> str:
    try:
        decoded = urlsafe_b64decode(value.encode("utf-8"))
        if len(decoded) == 32:
            return value
    except Exception:
        pass

    return _derive_fernet_key(value)


def _default_database_url() -> str:
    if Path("/.dockerenv").exists():
        return "sqlite:////app/data/app.db"

    return "sqlite:///./app.db"


management_secret = os.getenv("MANAGEMENT_SECRET", "change-me-in-production")
token_encryption_key = os.getenv(
    "TOKEN_ENCRYPTION_KEY",
    _derive_fernet_key(management_secret),
)


settings = Settings(
    app_name=os.getenv("APP_NAME", "YT Download API"),
    api_prefix=os.getenv("API_PREFIX", "/api/v1"),
    allowed_origins=[
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
        if origin.strip()
    ],
    temp_dir_prefix=os.getenv("TEMP_DIR_PREFIX", "yt-download-"),
    request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "300")),
    database_url=os.getenv("DATABASE_URL", _default_database_url()),
    management_secret=management_secret,
    token_encryption_key=_normalize_fernet_key(token_encryption_key),
    youtube_cookiefile=os.getenv("YOUTUBE_COOKIEFILE") or None,
    youtube_po_token=os.getenv("YOUTUBE_PO_TOKEN") or None,
    faster_whisper_model=os.getenv("FASTER_WHISPER_MODEL", "tiny"),
    faster_whisper_device=os.getenv("FASTER_WHISPER_DEVICE", "cpu"),
    faster_whisper_compute_type=os.getenv("FASTER_WHISPER_COMPUTE_TYPE", "int8"),
    faster_whisper_cpu_threads=int(os.getenv("FASTER_WHISPER_CPU_THREADS", "0")),
)
