from dataclasses import dataclass
from typing import Literal

from app.agents.base import BaseAgent
from app.config import Settings, get_settings

DataMode = Literal["listing_mode", "demo_listing_mode", "area_mode"]


@dataclass
class DataAvailabilityDecision:
    mode: DataMode
    data_warning: str | None
    real_count: int
    demo_count: int


class DataAvailabilityAgent(BaseAgent):
    name = "data_availability_agent"

    def __init__(self, *, settings: Settings | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.settings = settings or get_settings()

    def decide_mode(
        self,
        *,
        available_real_count: int,
        available_demo_count: int,
        allow_demo: bool,
    ) -> DataAvailabilityDecision:
        if available_real_count > 0:
            return DataAvailabilityDecision(
                mode="listing_mode",
                data_warning=None,
                real_count=available_real_count,
                demo_count=available_demo_count,
            )
        if allow_demo and self.settings.enable_demo_rental_data and available_demo_count > 0:
            return DataAvailabilityDecision(
                mode="demo_listing_mode",
                data_warning="当前为 demo 样例房源，仅用于演示算法和地图通勤，不代表真实可租房源。",
                real_count=available_real_count,
                demo_count=available_demo_count,
            )
        return DataAvailabilityDecision(
            mode="area_mode",
            data_warning="当前系统尚未接入真实租房平台或公司库存数据；以下仅推荐上海区域/地铁站/板块方向，不推荐具体房子。",
            real_count=available_real_count,
            demo_count=available_demo_count,
        )

