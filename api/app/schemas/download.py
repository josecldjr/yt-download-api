from pydantic import BaseModel, Field


class DownloadRequest(BaseModel):
    url: str = Field(..., description="Public YouTube URL to download")
