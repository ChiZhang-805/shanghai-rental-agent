import json
from typing import Any

from pydantic import BaseModel

from app.config import Settings, get_effective_settings


class OpenAIUnavailableError(RuntimeError):
    pass


class OpenAIService:
    """The only place in the app that imports and creates an OpenAI client."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_effective_settings()
        self._client: Any | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.openai_api_key)

    @property
    def client(self) -> Any:
        if not self.is_configured:
            raise OpenAIUnavailableError("OPENAI_API_KEY is not configured.")
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise OpenAIUnavailableError("openai Python package is not installed.") from exc

            self._client = OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.settings.openai_request_timeout_seconds,
                max_retries=self.settings.openai_max_retries,
            )
        return self._client

    def generate_json(
        self,
        *,
        prompt: str,
        schema_model: type[BaseModel] | None = None,
        schema: dict[str, Any] | None = None,
        schema_name: str = "structured_output",
        model: str | None = None,
        fallback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            if fallback is not None:
                return fallback
            raise OpenAIUnavailableError("OPENAI_API_KEY is not configured.")

        json_schema = schema or (schema_model.model_json_schema() if schema_model else None)
        if json_schema is None:
            raise ValueError("schema or schema_model is required for structured output.")

        try:
            response = self.client.responses.create(
                model=model or self.settings.openai_responses_model,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": json_schema,
                        "strict": True,
                    }
                },
            )
            return json.loads(self._response_text(response))
        except Exception as exc:
            if fallback is not None:
                return fallback
            if isinstance(exc, OpenAIUnavailableError):
                raise
            raise OpenAIUnavailableError(str(exc)) from exc

    def generate_text(
        self,
        *,
        prompt: str,
        model: str | None = None,
        fallback: str | None = None,
    ) -> str:
        if not self.is_configured:
            if fallback is not None:
                return fallback
            raise OpenAIUnavailableError("OPENAI_API_KEY is not configured.")
        try:
            response = self.client.responses.create(
                model=model or self.settings.openai_responses_model,
                input=prompt,
            )
            return self._response_text(response)
        except Exception as exc:
            if fallback is not None:
                return fallback
            if isinstance(exc, OpenAIUnavailableError):
                raise
            raise OpenAIUnavailableError(str(exc)) from exc

    def embed_texts(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        if not self.is_configured:
            raise OpenAIUnavailableError("OPENAI_API_KEY is not configured.")
        try:
            response = self.client.embeddings.create(
                model=model or self.settings.openai_embedding_model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            if isinstance(exc, OpenAIUnavailableError):
                raise
            raise OpenAIUnavailableError(str(exc)) from exc

    def analyze_image_json(
        self,
        *,
        prompt: str,
        image_data_url: str,
        schema_model: type[BaseModel],
        schema_name: str = "image_analysis",
        fallback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            if fallback is not None:
                return fallback
            raise OpenAIUnavailableError("OPENAI_API_KEY is not configured.")
        try:
            response = self.client.responses.create(
                model=self.settings.openai_vision_model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": image_data_url},
                        ],
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": schema_model.model_json_schema(),
                        "strict": True,
                    }
                },
            )
            return json.loads(self._response_text(response))
        except Exception as exc:
            if fallback is not None:
                return fallback
            if isinstance(exc, OpenAIUnavailableError):
                raise
            raise OpenAIUnavailableError(str(exc)) from exc

    @staticmethod
    def _response_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text
        chunks: list[str] = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    chunks.append(text)
        if chunks:
            return "\n".join(chunks)
        raise RuntimeError("OpenAI response did not include text output.")
