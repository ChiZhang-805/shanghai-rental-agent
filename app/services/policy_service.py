from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.policy import PolicyChunk, PolicyDocument
from app.schemas.policy import PolicyAnswer, PolicyBasis, PolicyIngestResponse
from app.services.city_guard import CityGuard
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import chunk_text, keyword_score


@dataclass
class PolicyChunkRecord:
    title: str
    source_org: str
    source_url: str
    doc_type: str
    content: str
    score: float = 0.0


class PolicyService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        city_guard: CityGuard | None = None,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.city_guard = city_guard or CityGuard()
        self.settings = get_settings()

    def ingest_directory(self, session: Session, directory: Path = Path("data/policies")) -> PolicyIngestResponse:
        records = self.load_policy_files(directory)
        session.execute(delete(PolicyChunk))
        session.execute(delete(PolicyDocument))
        documents = 0
        chunks = 0
        for meta, raw_text in records:
            document = PolicyDocument(
                title=meta["title"],
                source_org=meta["source_org"],
                source_url=meta["source_url"],
                published_at=self._parse_date(meta.get("published_at")),
                effective_from=self._parse_date(meta.get("effective_from")),
                effective_to=self._parse_date(meta.get("effective_to")),
                doc_type=meta.get("doc_type", "general"),
                raw_text=raw_text,
            )
            session.add(document)
            session.flush()
            chunk_values = chunk_text(raw_text)
            embeddings = self.embedding_service.embed_texts(chunk_values)
            for index, (content, embedding) in enumerate(zip(chunk_values, embeddings, strict=False)):
                session.add(
                    PolicyChunk(
                        document_id=document.id,
                        chunk_index=index,
                        content=content,
                        embedding=embedding,
                    )
                )
                chunks += 1
            documents += 1
        session.commit()
        return PolicyIngestResponse(documents=documents, chunks=chunks)

    def answer(
        self,
        question: str,
        *,
        session: Session | None = None,
        chunks: list[PolicyChunkRecord] | None = None,
    ) -> PolicyAnswer:
        self.city_guard.assert_request_allowed(question)
        matches = self.retrieve(question, session=session, chunks=chunks)
        if not matches:
            return PolicyAnswer(
                answer="本地政策库没有检索到可引用来源，不能基于无来源内容回答该政策问题。",
                policy_basis=[],
                needs_human=False,
            )
        basis = [
            PolicyBasis(
                title=record.title,
                source_org=record.source_org,
                source_url=record.source_url,
                chunk=record.content[:320],
            )
            for record in matches
        ]
        answer_lines = [
            "根据本地上海政策库检索结果，可先按以下口径处理：",
            self._summarize_from_matches(question, matches),
            "如涉及合同争议、税费争议、定金争议、产权/抵押/查封/户口等个案，请转人工复核。",
        ]
        return PolicyAnswer(
            answer="\n".join(answer_lines),
            policy_basis=basis,
            needs_human=self._needs_human(question),
        )

    def retrieve(
        self,
        question: str,
        *,
        session: Session | None = None,
        chunks: list[PolicyChunkRecord] | None = None,
        top_k: int | None = None,
    ) -> list[PolicyChunkRecord]:
        source_chunks = chunks if chunks is not None else self.fetch_chunks(session)
        scored: list[PolicyChunkRecord] = []
        for record in source_chunks:
            score = keyword_score(question, record.content)
            if score > 0:
                scored.append(
                    PolicyChunkRecord(
                        title=record.title,
                        source_org=record.source_org,
                        source_url=record.source_url,
                        doc_type=record.doc_type,
                        content=record.content,
                        score=score,
                    )
                )
        scored.sort(key=lambda record: record.score, reverse=True)
        return scored[: top_k or self.settings.policy_top_k]

    def fetch_chunks(self, session: Session | None = None) -> list[PolicyChunkRecord]:
        if session is None:
            return self.local_policy_chunks(Path("data/policies"))
        stmt = (
            select(PolicyChunk, PolicyDocument)
            .join(PolicyDocument, PolicyDocument.id == PolicyChunk.document_id)
            .where(PolicyDocument.is_active.is_(True))
        )
        records: list[PolicyChunkRecord] = []
        for chunk, document in session.execute(stmt).all():
            records.append(
                PolicyChunkRecord(
                    title=document.title,
                    source_org=document.source_org,
                    source_url=document.source_url,
                    doc_type=document.doc_type,
                    content=chunk.content,
                )
            )
        return records

    def local_policy_chunks(self, directory: Path) -> list[PolicyChunkRecord]:
        records: list[PolicyChunkRecord] = []
        for meta, raw_text in self.load_policy_files(directory):
            for content in chunk_text(raw_text):
                records.append(
                    PolicyChunkRecord(
                        title=meta["title"],
                        source_org=meta["source_org"],
                        source_url=meta["source_url"],
                        doc_type=meta.get("doc_type", "general"),
                        content=content,
                    )
                )
        return records

    @staticmethod
    def load_policy_files(directory: Path) -> list[tuple[dict[str, str], str]]:
        if not directory.exists():
            return []
        files: list[tuple[dict[str, str], str]] = []
        for path in sorted(directory.glob("*.md")):
            meta, body = PolicyService.parse_policy_markdown(path.read_text(encoding="utf-8"))
            files.append((meta, body))
        return files

    @staticmethod
    def parse_policy_markdown(text: str) -> tuple[dict[str, str], str]:
        if not text.startswith("---"):
            return (
                {
                    "title": "未命名政策",
                    "source_org": "本地政策库",
                    "source_url": "",
                    "doc_type": "general",
                },
                text,
            )
        _, front_matter, body = text.split("---", 2)
        meta: dict[str, str] = {}
        for line in front_matter.strip().splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
        meta.setdefault("title", "未命名政策")
        meta.setdefault("source_org", "本地政策库")
        meta.setdefault("source_url", "")
        meta.setdefault("doc_type", "general")
        return meta, body.strip()

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if not value:
            return None
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _needs_human(question: str) -> bool:
        return any(keyword in question for keyword in ["争议", "纠纷", "定金", "产权", "抵押", "查封", "户口", "税费"])

    @staticmethod
    def _summarize_from_matches(question: str, matches: list[PolicyChunkRecord]) -> str:
        snippets: list[str] = []
        for record in matches[:3]:
            sentences = [part.strip() for part in record.content.replace("\n", "。").split("。") if part.strip()]
            selected = sentences[:2]
            snippets.append(f"《{record.title}》：" + "；".join(selected))
        return "\n".join(snippets)

