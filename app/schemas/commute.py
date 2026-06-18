from typing import Literal

from pydantic import BaseModel, Field


CommuteMode = Literal["transit", "driving", "walking", "bicycling", "electrobike"]
RouteStatus = Literal["ok", "error", "unavailable"]


class CoordinatePoint(BaseModel):
    label: str | None = None
    address: str | None = None
    lng: float | None = None
    lat: float | None = None


class CommuteRouteSummary(BaseModel):
    anchor_label: str
    mode: CommuteMode | str
    duration_min: float | None
    distance_m: int | None
    transfers: int | None = None
    walking_distance_m: int | None = None
    summary: str | None = None
    route_status: RouteStatus
    route_geojson: dict | None = None


class CommuteEstimateRequest(BaseModel):
    origin: CoordinatePoint
    destination: CoordinatePoint
    modes: list[CommuteMode] = Field(default_factory=lambda: ["transit"], min_length=1)
    city: str = "上海"


class CommuteEstimateResponse(BaseModel):
    city: str = "上海"
    routes: list[CommuteRouteSummary]
    unavailable_reason: str | None = None
