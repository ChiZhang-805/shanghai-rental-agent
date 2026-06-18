from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.document import Document, DocumentChunk
from app.schemas.documents import DocumentAnswer, DocumentUploadResponse
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import chunk_text, keyword_score


class DocumentService:
    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.settings = get_settings()

    def save_and_ingest(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None,
        session: Session | None = None,
    ) -> DocumentUploadResponse:
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name
        path = self.settings.upload_dir / safe_name
        path.write_bytes(content)
        raw_text = self.extract_text(path, content_type)
        chunks = chunk_text(raw_text)
        if session is None:
            return DocumentUploadResponse(document_id=None, filename=safe_name, chunks=len(chunks))

        document = Document(
            filename=safe_name,
            content_type=content_type,
            path=str(path),
            raw_text=raw_text,
        )
        session.add(document)
        session.flush()
        embeddings = self.embedding_service.embed_texts(chunks)
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=chunk,
                    embedding=embedding,
                )
            )
        session.commit()
        return DocumentUploadResponse(document_id=document.id, filename=safe_name, chunks=len(chunks))

    def answer(
        self,
        question: str,
        *,
        session: Session | None = None,
        document_id: int | None = None,
        chunks: list[str] | None = None,
    ) -> DocumentAnswer:
        source_chunks = chunks or self._fetch_chunks(session, document_id)
        scored = sorted(
            [(chunk, keyword_score(question, chunk)) for chunk in source_chunks],
            key=lambda pair: pair[1],
            reverse=True,
        )
        matches = [chunk for chunk, score in scored[: self.settings.document_top_k] if score > 0]
        if not matches:
            return DocumentAnswer(answer="文档中没有检索到可引用片段，不能给出结论。", basis=[], needs_human=False)
        needs_human = any(keyword in question for keyword in ["争议", "起诉", "违约", "税费", "产权", "抵押"])
        return DocumentAnswer(
            answer="根据上传文档片段，可做事实性摘录；涉及法律结论请转人工或律师复核。",
            basis=matches,
            needs_human=needs_human,
        )

    @staticmethod
    def extract_text(path: Path, content_type: str | None) -> str:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"} or (content_type or "").startswith("text/"):
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(path))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception:
                return path.read_bytes().decode("utf-8", errors="ignore")
        return path.read_bytes().decode("utf-8", errors="ignore")

    @staticmethod
    def _fetch_chunks(session: Session | None, document_id: int | None) -> list[str]:
        if session is None:
            return []
        stmt = select(DocumentChunk.content)
        if document_id is not None:
            stmt = stmt.where(DocumentChunk.document_id == document_id)
        return list(session.scalars(stmt).all())

