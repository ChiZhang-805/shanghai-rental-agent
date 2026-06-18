import re

from app.agents.base import BaseAgent
from app.schemas.customer_need import CustomerNeed


class CustomerNeedAgent(BaseAgent):
    name = "customer_need_agent"

    def extract(self, text: str) -> CustomerNeed:
        self.city_guard.assert_request_allowed(text)
        purpose = self._extract_purpose(text)
        budget_min, budget_max = self._extract_budget(text, purpose)
        rooms_min, rooms_max = self._extract_rooms(text)
        area_min, area_max = self._extract_area(text)
        commute = self._extract_commute(text)
        return CustomerNeed(
            city="上海",
            purpose=purpose,
            districts=self.city_guard.normalize_districts(text),
            budget_min=budget_min,
            budget_max=budget_max,
            rooms_min=rooms_min,
            rooms_max=rooms_max,
            area_min=area_min,
            area_max=area_max,
            commute_requirements=commute,
            must_haves=self._extract_must_haves(text),
            raw_text=text,
        )

    @staticmethod
    def _extract_purpose(text: str) -> str | None:
        if any(keyword in text for keyword in ["租房", "出租", "月租", "租金", "整租"]):
            return "rent"
        if any(keyword in text for keyword in ["买房", "购房", "购买", "想买", "出售", "二手房", "总价"]):
            return "sale"
        return None

    @staticmethod
    def _extract_budget(text: str, purpose: str | None) -> tuple[int | None, int | None]:
        range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-到至]\s*(\d+(?:\.\d+)?)\s*万", text)
        if range_match:
            return (
                int(float(range_match.group(1)) * 10000),
                int(float(range_match.group(2)) * 10000),
            )

        wan_matches = [int(float(value) * 10000) for value in re.findall(r"(\d+(?:\.\d+)?)\s*万", text)]
        yuan_matches = [
            int(value)
            for value in re.findall(r"(\d{4,9})\s*(?:元|块)?(?:/月|每月|月租|租金)?", text)
        ]
        values = wan_matches or yuan_matches
        if not values:
            return None, None
        value = values[0]
        if any(keyword in text for keyword in ["以上", "起", "至少", "不低于"]):
            return value, None
        if any(keyword in text for keyword in ["以内", "以下", "不超过", "最多", "预算"]):
            return None, value
        if purpose == "rent" and value > 200000:
            value = int(value / 10000)
        return None, value

    @staticmethod
    def _extract_rooms(text: str) -> tuple[int | None, int | None]:
        cn = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6}
        match = re.search(r"([一二两三四五六]|\d+)\s*(?:房|室)", text)
        if not match:
            return None, None
        raw = match.group(1)
        rooms = cn.get(raw, int(raw) if raw.isdigit() else None)
        if rooms is None:
            return None, None
        if any(keyword in text for keyword in ["以上", "至少", "不低于"]):
            return rooms, None
        return rooms, rooms

    @staticmethod
    def _extract_area(text: str) -> tuple[float | None, float | None]:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:平|平方米|㎡)", text)
        if not match:
            return None, None
        area = float(match.group(1))
        if any(keyword in text for keyword in ["以上", "至少", "不低于"]):
            return area, None
        if any(keyword in text for keyword in ["以内", "以下", "不超过"]):
            return None, area
        return area, area

    @staticmethod
    def _extract_commute(text: str) -> str | None:
        if any(keyword in text for keyword in ["通勤", "地铁", "上班", "公司"]):
            return text
        return None

    @staticmethod
    def _extract_must_haves(text: str) -> list[str]:
        keywords = ["电梯", "近地铁", "车位", "精装", "南北通", "拎包入住"]
        return [keyword for keyword in keywords if keyword in text]
