from pydantic import BaseModel


class GeocodeRequest(BaseModel):
    address: str
    city: str = "上海"


class GeocodeResponse(BaseModel):
    address: str
    city: str = "上海"
    district: str | None = None
    lng: float | None = None
    lat: float | None = None
    coordinate_system: str = "gcj02"
    provider: str = "amap"
    status: str = "unavailable"
    message: str | None = None

