from pydantic import BaseModel

from app.config import Settings
from app.services.embedding_service import EmbeddingService
from app.services.openai_service import OpenAIService, OpenAIUnavailableError


class TinyPayload(BaseModel):
    ok: bool


def test_generate_json_returns_fallback_when_sdk_missing() -> None:
    service = OpenAIService(Settings(openai_api_key="sk-test"))
    service._client = BrokenClient()  # noqa: SLF001

    assert service.generate_json(
        prompt="return json",
        schema_model=TinyPayload,
        fallback={"ok": True},
    ) == {"ok": True}


def test_generate_text_returns_fallback_when_sdk_missing() -> None:
    service = OpenAIService(Settings(openai_api_key="sk-test"))
    service._client = BrokenClient()  # noqa: SLF001

    assert service.generate_text(prompt="hello", fallback="fallback") == "fallback"


def test_embedding_service_uses_deterministic_fallback_when_openai_unavailable() -> None:
    embedding = EmbeddingService(openai_service=BrokenEmbeddingService()).embed_text("上海租房")

    assert len(embedding) == 1536


class BrokenClient:
    responses = None

    def __init__(self) -> None:
        self.responses = self

    def create(self, **kwargs):
        raise RuntimeError("OpenAI unavailable")


class BrokenEmbeddingService:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise OpenAIUnavailableError("OpenAI unavailable")
