from pydantic import BaseModel, Field


class AccessTokenBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Display name for the token.")
    description: str = Field(default="", description="Optional token description.")


class AccessTokenCreate(AccessTokenBase):
    content: str = Field(..., min_length=1, description="Plain-text token content.")


class AccessTokenUpdate(AccessTokenBase):
    content: str = Field(..., min_length=1, description="Updated plain-text token content.")


class AccessTokenResponse(AccessTokenBase):
    id: str
    content: str

    model_config = {"from_attributes": True}
