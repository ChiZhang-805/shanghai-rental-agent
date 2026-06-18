from pydantic import BaseModel, Field


class MapLayerResponse(BaseModel):
    center: dict[str, float]
    zoom: int = 12
    markers_geojson: dict
    routes_geojson: dict
    areas_geojson: dict | None = None
    legend: dict = Field(default_factory=dict)

