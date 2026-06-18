import hashlib
import math

from app.config import Settings, get_settings
from app.services.openai_service import OpenAIService, OpenAIUnavailableError


class EmbeddingService:
    def __init__(
        self,
        openai_service: OpenAIService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.openai_service = openai_service or OpenAIService(self.settings)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            return self.openai_service.embed_texts(texts)
        except OpenAIUnavailableError:
            return [self.deterministic_embedding(text, self.settings.openai_embedding_dim) for text in texts]

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    @staticmethod
    def deterministic_embedding(text: str, dimensions: int = 1536) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(dimensions)]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

