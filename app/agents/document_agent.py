from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.schemas.documents import DocumentAnswer
from app.services.document_service import DocumentService


class DocumentAgent(BaseAgent):
    name = "document_agent"

    def __init__(self, *, document_service: DocumentService | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.document_service = document_service or DocumentService()

    def answer(
        self,
        question: str,
        *,
        session: Session | None = None,
        document_id: int | None = None,
    ) -> DocumentAnswer:
        self.city_guard.assert_request_allowed(question)
        return self.document_service.answer(question, session=session, document_id=document_id)

