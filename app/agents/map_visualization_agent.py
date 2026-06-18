from app.agents.base import BaseAgent
from app.schemas.map import MapLayerResponse
from app.schemas.rental import RentalRecommendationItem
from app.services.map_layer_service import MapLayerService


class MapVisualizationAgent(BaseAgent):
    name = "map_visualization_agent"

    def __init__(self, *, map_layer_service: MapLayerService | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.map_layer_service = map_layer_service or MapLayerService(self.city_guard)

    def build_layers(self, items: list[RentalRecommendationItem]) -> MapLayerResponse:
        return self.map_layer_service.build_layers(items)

