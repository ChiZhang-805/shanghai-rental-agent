from app.agents.data_availability_agent import DataAvailabilityAgent
from app.config import Settings


def test_data_availability_modes() -> None:
    agent = DataAvailabilityAgent(settings=Settings(enable_demo_rental_data=True))
    assert agent.decide_mode(available_real_count=1, available_demo_count=3, allow_demo=True).mode == "listing_mode"
    assert agent.decide_mode(available_real_count=0, available_demo_count=3, allow_demo=True).mode == "demo_listing_mode"
    assert agent.decide_mode(available_real_count=0, available_demo_count=3, allow_demo=False).mode == "area_mode"

