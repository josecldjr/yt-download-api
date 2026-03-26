import os

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str
    api_prefix: str
    allowed_origins: list[str]
    temp_dir_prefix: str
    request_timeout_seconds: int


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
)
