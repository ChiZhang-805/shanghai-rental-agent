from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.rental import RentalPreferenceWeights


class SocialCriterion(BaseModel):
    name: str
    importance: Literal["low", "medium", "high"] = "medium"
    scoring_hint: str


class SocialInsightRequest(BaseModel):
    source_type: Literal["pasted_text", "uploaded_image"] = "pasted_text"
    text: str | None = None
    image_path: str | None = None
    user_context: str | None = None


class SocialInsightResponse(BaseModel):
    extracted_text: str | None = None
    criteria: list[SocialCriterion] = Field(default_factory=list)
    suggested_weights: RentalPreferenceWeights = Field(default_factory=RentalPreferenceWeights)
    caution_notes: list[str] = Field(default_factory=list)

