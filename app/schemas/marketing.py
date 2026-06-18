from pydantic import BaseModel, ConfigDict, Field


class MarketingGenerateRequest(BaseModel):
    listing_id: int | None = None
    listing: dict | None = None
    channel: str = "朋友圈"
    tone: str = "专业、真实、克制"


class MarketingGenerateResponse(BaseModel):
    allowed: bool
    copy_text: str = Field(default="", validation_alias="copy", serialization_alias="copy")
    channel: str
    requires_human_review: bool = True
    refusal_reason: str | None = None
    risk_flags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)
