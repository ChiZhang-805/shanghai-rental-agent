from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.commute import CommuteMode, CommuteRouteSummary
from app.schemas.map import MapLayerResponse


class AnchorInput(BaseModel):
    label: str
    address: str | None = None
    lng: float | None = None
    lat: float | None = None
    anchor_type: Literal["workplace", "school", "family", "frequent_place", "other"] = "workplace"
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    arrival_time: str | None = None


class RentalPreferenceWeights(BaseModel):
    commute: float = Field(default=0.35, ge=0.0, le=1.0)
    budget: float = Field(default=0.25, ge=0.0, le=1.0)
    transit_access: float = Field(default=0.15, ge=0.0, le=1.0)
    listing_quality: float = Field(default=0.10, ge=0.0, le=1.0)
    amenities: float = Field(default=0.10, ge=0.0, le=1.0)
    risk: float = Field(default=0.05, ge=0.0, le=1.0)


class RentalRecommendationRequest(BaseModel):
    query: str | None = None
    customer_id: int | None = Field(default=None, ge=1)
    budget_monthly: int | None = Field(default=None, ge=0)
    min_rent_monthly: int | None = Field(default=None, ge=0)
    max_rent_monthly: int | None = Field(default=None, ge=0)
    rooms: int | None = Field(default=None, ge=1, le=10)
    preferred_districts: list[str] = Field(default_factory=list)
    excluded_districts: list[str] = Field(default_factory=list)
    anchors: list[AnchorInput] = Field(default_factory=list)
    max_commute_min: int = Field(default=45, ge=5, le=180)
    commute_modes: list[CommuteMode] = Field(default_factory=lambda: ["transit"], min_length=1)
    weights: RentalPreferenceWeights = Field(default_factory=RentalPreferenceWeights)
    require_metro_distance_m: int | None = Field(default=None, ge=0)
    allow_demo_data: bool = False
    recommendation_unit: Literal["auto", "community"] = "community"
    result_limit: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def validate_rent_range(self) -> "RentalRecommendationRequest":
        if (
            self.min_rent_monthly is not None
            and self.max_rent_monthly is not None
            and self.min_rent_monthly > self.max_rent_monthly
        ):
            raise ValueError("min_rent_monthly 不能大于 max_rent_monthly")
        return self


class RentalRecommendationItem(BaseModel):
    item_type: Literal["listing", "area", "community"]
    id: str
    title: str
    city: str = "上海"
    district: str | None
    community_name: str | None = None
    address: str | None = None
    lng: float
    lat: float
    rent_monthly: int | None = None
    room_rents: dict[str, int] | None = None
    is_demo: bool
    data_source: str
    total_score: float
    score_breakdown: dict[str, float]
    commute_routes: list[CommuteRouteSummary]
    recommendation_reason: str
    risk_notes: list[str]
    next_action: str


class RentalRecommendationResponse(BaseModel):
    mode: Literal["area_mode", "listing_mode", "demo_listing_mode"]
    data_warning: str | None
    request_summary: dict
    results: list[RentalRecommendationItem]
    map_layers: MapLayerResponse
    audit_id: str | None = None
