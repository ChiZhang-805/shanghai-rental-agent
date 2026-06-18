from pydantic import BaseModel, Field

SHANGHAI_DISTRICTS: list[str] = [
    "黄浦",
    "徐汇",
    "长宁",
    "静安",
    "普陀",
    "虹口",
    "杨浦",
    "闵行",
    "宝山",
    "嘉定",
    "浦东",
    "金山",
    "松江",
    "青浦",
    "奉贤",
    "崇明",
]

OUTSIDE_SHANGHAI_CITY_KEYWORDS: list[str] = [
    "昆山",
    "花桥",
    "苏州",
    "太仓",
    "嘉善",
    "嘉兴",
    "杭州",
    "南通",
    "无锡",
    "南京",
    "北京",
    "深圳",
    "广州",
    "成都",
    "武汉",
    "杭州湾",
]


class CityGuardResult(BaseModel):
    allowed: bool
    city: str = "上海"
    districts: list[str] = Field(default_factory=list)
    outside_keywords: list[str] = Field(default_factory=list)
    reason: str = ""


class ErrorResponse(BaseModel):
    detail: str
    needs_human: bool = False

