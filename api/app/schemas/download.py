from pydantic import BaseModel, Field

from app.schemas.api_configuration import DownloadQuality


class DownloadRequest(BaseModel):
    url: str = Field(
        ...,
        description="Public YouTube video URL.",
        examples=[
            "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "https://www.youtube.com/watch?v=mti4V1c5UaY",
        ],
    )
    quality: DownloadQuality = Field(
        default="1080p",
        description="Requested maximum output quality.",
        examples=["720p", "1080p", "1440p", "4k", "best"],
    )
