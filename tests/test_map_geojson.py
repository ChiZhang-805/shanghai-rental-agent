from app.schemas.rental import RentalRecommendationItem
from app.services.map_layer_service import MapLayerService


def test_map_layer_geojson_format_and_coordinates() -> None:
    item = RentalRecommendationItem(
        item_type="area",
        id="A1",
        title="张江高科周边",
        district="浦东",
        lng=121.598,
        lat=31.207,
        is_demo=True,
        data_source="candidate_area",
        total_score=82.5,
        score_breakdown={"commute": 30, "budget": 90, "transit_access": 100, "listing_quality": 70, "amenities": 70, "risk": 80},
        commute_routes=[],
        recommendation_reason="区域推荐",
        risk_notes=["demo"],
        next_action="核验真实房源",
    )
    layers = MapLayerService().build_layers([item])
    assert layers.markers_geojson["type"] == "FeatureCollection"
    feature = layers.markers_geojson["features"][0]
    assert feature["geometry"]["type"] == "Point"
    lng, lat = feature["geometry"]["coordinates"]
    assert 120.85 <= lng <= 122.25
    assert 30.67 <= lat <= 31.90

