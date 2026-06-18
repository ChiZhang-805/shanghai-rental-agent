from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: int | None = None
    filename: str
    chunks: int


class DocumentQuestionRequest(BaseModel):
    question: str
    document_id: int | None = None


class DocumentAnswer(BaseModel):
    answer: str
    basis: list[str] = Field(default_factory=list)
    needs_human: bool = False

