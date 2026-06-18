from app.agents.social_insight_agent import SocialInsightAgent
from app.schemas.social_insight import SocialInsightRequest
from app.services.social_insight_service import SocialInsightService


class BrokenSession:
    def __init__(self) -> None:
        self.rolled_back = False

    def add(self, value: object) -> None:
        return None

    def commit(self) -> None:
        raise RuntimeError("database unavailable")

    def rollback(self) -> None:
        self.rolled_back = True


def test_social_insight_returns_when_persistence_fails() -> None:
    session = BrokenSession()
    response = SocialInsightService().extract(
        SocialInsightRequest(text="预算要稳，通勤别太久，最好靠近地铁"),
        session=session,  # type: ignore[arg-type]
    )

    assert response.criteria
    assert session.rolled_back is True


def test_social_insight_allows_negative_outside_city_reference() -> None:
    response = SocialInsightAgent().extract(
        SocialInsightRequest(text="不要租昆山，还是只看上海，最好通勤短一点。")
    )

    assert response.extracted_text


def test_social_insight_rejects_image_path_outside_upload_dir() -> None:
    response = SocialInsightService().extract(
        SocialInsightRequest(source_type="uploaded_image", image_path="/etc/passwd")
    )

    assert any("图片路径不在允许上传目录" in note for note in response.caution_notes)
