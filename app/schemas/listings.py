from pydantic import BaseModel, ConfigDict, Field


class ListingSearchRequest(BaseModel):
    query: str | None = None
    purpose: str | None = Field(default=None, pattern="^(sale|rent)$")
    city: str = "上海"
    districts: list[str] = Field(default_factory=list)
    budget_min: int | None = None
    budget_max: int | None = None
    rooms_min: int | None = None
    rooms_max: int | None = None
    top_k: int = 10


class ListingOut(BaseModel):
    id: int | None = None
    listing_code: str
    city: str = "上海"
    district: str
    subdistrict: str | None = None
    community_name: str
    title: str
    purpose: str
    rooms: int | None = None
    halls: int | None = None
    bathrooms: int | None = None
    area_sqm: float
    sale_price_total: int | None = None
    rent_price_monthly: int | None = None
    verification_status: str
    entrusted_status: str
    listing_status: str
    score: float | None = None
    recommendation_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ListingSearchResponse(BaseModel):
    city: str = "上海"
    results: list[ListingOut]
    refusal_reason: str | None = None

