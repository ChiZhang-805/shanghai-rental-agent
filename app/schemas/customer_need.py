from pydantic import BaseModel, Field


class CustomerNeed(BaseModel):
    city: str = "上海"
    purpose: str | None = None
    districts: list[str] = Field(default_factory=list)
    budget_min: int | None = None
    budget_max: int | None = None
    rooms_min: int | None = None
    rooms_max: int | None = None
    area_min: float | None = None
    area_max: float | None = None
    commute_requirements: str | None = None
    must_haves: list[str] = Field(default_factory=list)
    raw_text: str

