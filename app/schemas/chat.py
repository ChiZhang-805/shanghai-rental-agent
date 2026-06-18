from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    intent: str
    answer: str
    city: str = "上海"
    needs_human: bool = False
    data: dict = Field(default_factory=dict)

