from typing import Literal

from pydantic import BaseModel, Field


class PublicApiConfigurationResponse(BaseModel):
    require_api_authentication: bool = Field(
        ...,
        description="Whether the download endpoint currently requires an API access token.",
    )
    default_quality: str = Field(..., description="Default quality value used by the frontend.")
    quality_options: list[str] = Field(..., description="Available download quality options.")


class AdminApiConfigurationResponse(PublicApiConfigurationResponse):
    pass


class AdminApiConfigurationUpdate(BaseModel):
    require_api_authentication: bool = Field(
        ...,
        description="Whether clients must send a Bearer token to download videos.",
    )


DownloadQuality = Literal["144p", "360p", "480p", "720p", "1080p", "1440p", "4k", "best"]
