from pydantic import BaseModel, Field


class DownloadRequest(BaseModel):
    url: str = Field(
        ...,
        description="Public YouTube video URL.",
        examples=[
            "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "https://www.youtube.com/watch?v=mti4V1c5UaY",
        ],
    )
